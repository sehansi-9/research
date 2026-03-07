from typing import List, Dict, Set
import asyncio
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, RemoveMessage
from app.core.config import settings
from app.core.prompts import get_system_prompt
from app.graph.state import AgentState
from app.graph.nodes.tools import tools
import json
import re

# Initialize LLMs based on available keys
if settings.deepseek_api_key:
    # Use DeepSeek (OpenAI-compatible)
    llm = ChatOpenAI(
        api_key=settings.deepseek_api_key,
        model_name=settings.llm_model,
        base_url="https://api.deepseek.com",
        temperature=0.1
    )
    summarizer_llm = ChatOpenAI(
        api_key=settings.deepseek_api_key,
        model_name=settings.summarizer_llm_model,
        base_url="https://api.deepseek.com",
        temperature=0
    )
    print("🚀 Using DeepSeek LLM")
else:
    # Use Groq (default)
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.llm_model,
        temperature=0.1
    )
    summarizer_llm = ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.summarizer_llm_model,
        temperature=0
    )
    print("🚀 Using Groq LLM")

def decode_hex_name(hex_str: str) -> str:
    """Decodes protobuf hex format to human readable string."""
    try:
        if not hex_str: return ""
        if '"value":"' in hex_str:
            match = re.search(r'"value":"([^"]+)"', hex_str)
            if match: hex_str = match.group(1)
        if all(c in '0123456789ABCDEFabcdef' for c in hex_str.lower()):
            return bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
        return hex_str
    except:
        return hex_str

async def detect_topic_shift(question: str, facts: List[str]) -> bool:
    """Uses a small model to judge if the new question is a different topic from the facts."""
    
    prompt = f"""[INQUIRY ANALYST MODE]
Evaluate if the NEW QUESTION is a follow-up to the CURRENT RESEARCH or a shift to a NEW SUBJECT.

RULES:
1. If the user uses pronouns (he, them, those, that) or says 'more about that', it is 'CONTINUED'.
2. If the user asks a brand-new question (e.g., 'Who is X?') and X is NOT in the CURRENT FACTS, it is 'NEW'.
3. If the user asks for more details about a person, role, or year already mentioned in the FACTS, it is 'CONTINUED'.
4. When in doubt, if the name/subject changes, reply 'NEW'.

CURRENT KNOWLEDGE POOL:
{facts[:12]}

NEW QUESTION:
{question}

RESULT (NEW/CONTINUED):"""
    try:
        res = await summarizer_llm.ainvoke([HumanMessage(content=prompt)])
        
        # Log token usage for the topic shift check
        if hasattr(res, 'response_metadata') and 'token_usage' in res.response_metadata:
            usage = res.response_metadata['token_usage']
            print(f"  📊 [Token Usage - Topic Shift]: Prompt: {usage.get('prompt_tokens', 0)}, Completion: {usage.get('completion_tokens', 0)}")
            
        return "NEW" in res.content.upper()
    except:
        return False

def heal_json(text: str) -> str:
    """Attempts to fix common LLM JSON formatting errors like trailing quotes."""
    text = text.strip()
    # Remove MD blocks if they got in there
    if text.startswith("```"):
        text = re.sub(r'^```json\s*|\s*```$', '', text, flags=re.MULTILINE)
    # Fix trailing quote error: ...}]" -> ...}]
    if text.endswith('"') and (text.count('"') % 2 != 0):
        text = text[:-1]
    # Ensure it ends with a brace or bracket
    if not text.endswith(('}', ']')):
        for char in reversed(text):
            if char in (']', '}'): break
            text = text[:-1]
    return text

async def distill_fact(tool_msg: ToolMessage, resolved_entities: dict) -> str:
    """Uses the 8B LLM to turn a raw JSON tool result into a technical fact, enriched with cached names."""
    try:
        if "attribute" in tool_msg.name or "error" in tool_msg.content.lower():
            return ""

        if len(tool_msg.content) < 200:
            return ""

        # PRE-PROCESS: Inject names from cache into JSON so LLM sees them
        content = tool_msg.content[:4000]
        for eid, name in list(resolved_entities.items())[-50:]:
            if eid in content:
                content = content.replace(eid, f"{name} ({eid})")
            
        if "search" in tool_msg.name.lower():
            prompt = f"""[ENTITY SEARCH EXTRACTOR]
Task: Extract the list of entities found in this search result.
Rules:
1. Simply list the entities found compactly (e.g., 'Found Entities: [Name (ID), Name (ID), ...]').
2. DO NOT invent or extract relationships, connections, or dates!
3. NO conversational filler.

DATA:
{content}

FACTS:"""
        elif "relation" in tool_msg.name.lower():
            prompt = f"""[RELATIONSHIP EXTRACTOR]
Task: Summarize the connections found in this JSON.
Rules:
1. In batch relations, the outer JSON KEYS are the Source Entities.
2. Formulate clearly: 'Entity [relatedEntityId] was connected to Entity [Outer JSON Key] from [startTime] to [endTime]'.
3. CRITICAL: field like "name" represent the RELATION TYPE, not a name.
4. ONLY include dates if they exist. NEVER treat IDs (like '2153-12') as dates!
5. You MUST INCLUDE the exact Source IDs and Target IDs (relatedEntityId).
6. NO conversational filler.

DATA:
{content}

FACTS:"""
        else:
            prompt = f"""[DATA EXTRACTOR]
Task: Extract the specific values and points from this JSON.
Rules:
1. Simply state the values compactly.
2. NO conversational filler.

DATA:
{content}

FACTS:"""
        res = await summarizer_llm.ainvoke([HumanMessage(content=prompt)])
        
        # Log token usage for the fact distillation
        if hasattr(res, 'response_metadata') and 'token_usage' in res.response_metadata:
            usage = res.response_metadata['token_usage']
            print(f"  📊 [Token Usage - Distill Fact]: Prompt: {usage.get('prompt_tokens', 0)}, Completion: {usage.get('completion_tokens', 0)}")
            
        fact_lines = [l.strip() for l in res.content.split("\n") if l.strip()][:5]
        fact = " | ".join(fact_lines)
            
        # CLEANUP: Remove empty artifacts
        fact = fact.replace("()", "").replace("''", "").replace("  ", " ")
        fact = fact.replace(" : ", ": ").replace("| |", "|")
        
        for j in ["The discovery is that ", "Technical discovery: ", "Subject: ", "Discovery: "]:
            fact = fact.replace(j, "")
            
        fact_clean = fact.strip().strip("|").strip()
        if len(fact_clean) < 15 or "No facts" in fact_clean:
            return ""
            
        return f"[{tool_msg.name}] {fact_clean}"
    except:
        return ""

# Agent Node
async def call_model(state: AgentState):
    print("\n[Node: Agent]")
    llm_with_tools = llm.bind_tools(tools)
    
    messages = state["messages"]
    facts = state.get("facts", [])
    entity_cache = state.get("entity_cache", {})

    # 1. TOPIC SHIFT & DEEP PURGE
    last_human_idx = -1
    for i in range(len(messages)-1, -1, -1):
        if messages[i].type == "human":
            last_human_idx = i
            break
            
    is_new_topic = await detect_topic_shift(messages[last_human_idx].content if last_human_idx != -1 else "", facts)
    
    delete_msgs = []
    # NEW LOGIC: Native State Purging via RemoveMessage
    if is_new_topic and messages[-1].type == "human":
        print("  🚫 New Topic Detected: Hard State Purge")
        facts = []
        entity_cache = {}
        # Start fresh: Only keep the latest human message
        current_history = [messages[last_human_idx]]
        
        # Schedule ALL previous messages for literal deletion from LangGraph state memory
        delete_msgs = [RemoveMessage(id=m.id) for m in messages[:last_human_idx] if hasattr(m, 'id') and m.id]
    else:
        # Standard Tiered Truncation for follow-ups
        current_history = messages
    
    # 2. Process Memory (Tiered Truncation)
    resolved_entities = entity_cache.copy()
    new_facts = []
    
    fresh_tool_msgs = []
    for msg in reversed(current_history):
        if msg.type == "tool": fresh_tool_msgs.append(msg)
        elif msg.type == "ai": break
            
    processed_messages = []
    tool_count = sum(1 for m in current_history if m.type == "tool")
    seen_tools = 0

    for i, msg in enumerate(current_history):
        if msg.type == "tool":
            seen_tools += 1
            try:
                data = json.loads(msg.content)
                extract_entities(data, resolved_entities)
                if msg in fresh_tool_msgs:
                    fact = await distill_fact(msg, resolved_entities)
                    if fact and fact not in facts:
                        print(f"  📝 New Fact: {fact}")
                        new_facts.append(fact)
                
                is_archive = (tool_count - seen_tools) > 4
                limit = 500 if is_archive else 2500
                content = msg.content
                if len(content) > limit:
                    content = content[:limit] + "... [ARCHIVED]"
                
                tool_name = "unknown_tool"
                for prev_msg in reversed(current_history[:i]):
                    if prev_msg.type == "ai" and hasattr(prev_msg, 'tool_calls'):
                        for tc in prev_msg.tool_calls:
                            if tc['id'] == msg.tool_call_id:
                                tool_name = tc['name']
                                break
                        if tool_name != "unknown_tool": break
                
                processed_messages.append(ToolMessage(content=content, tool_call_id=msg.tool_call_id, name=tool_name))
            except:
                processed_messages.append(msg)
        else:
            processed_messages.append(msg)

    # 3. FINAL CONTEXT FILTERING
    if is_new_topic:
        final_history = processed_messages # Already purged to just System + Latest Human
    elif len(processed_messages) > 10: # Tightened window to 10 for the daily token diet
        start_idx = len(processed_messages) - 9
        while start_idx > 1 and processed_messages[start_idx].type == "tool":
            start_idx -= 1
        final_history = [processed_messages[0]] + processed_messages[start_idx:]
    else:
        final_history = processed_messages

    # 4. Final Data Assembly
    updated_facts = facts + new_facts
    if len(updated_facts) > 15: updated_facts = updated_facts[-15:]
    facts_str = "\n".join([f"- {f}" for f in updated_facts])
    
    # Filter Entity Cache to remove IDs
    cache_str = " | ".join([f"Label for {k}:{v}" for k, v in list(resolved_entities.items())[-40:]])

    kinds_list = ", ".join([f"{k['major']}.{k['minor']}" for k in settings.entity_kinds])
    system_prompt = get_system_prompt()
    instructions = [
        system_prompt,
        f"\nSTRICT SCHEMA: {kinds_list}",
        f"KNOWLEDGE POOL EXCERPT:\n{facts_str if facts_str else 'Empty'}",
        f"ENTITY LOOKUP TABLE: {cache_str if cache_str else 'Empty'}",
    ]

    # 5. RECURSIVE INVOKE WITH RETRIES
    last_error = ""
    for attempt in range(3):
        try:
            current_prompt = [SystemMessage(content="\n".join(instructions))] + final_history
            if last_error:
                current_prompt.append(HumanMessage(content=f"SAFETY SYSTEM: Last tool call failed. Fix logic and resubmit JSON."))
                
            res = await llm_with_tools.ainvoke(current_prompt)
            
            # Log primary model token usage
            if hasattr(res, 'response_metadata') and 'token_usage' in res.response_metadata:
                usage = res.response_metadata['token_usage']
                print(f"  📊 [Token Usage - Primary LLM]: Prompt: {usage.get('prompt_tokens', 0)}, Completion: {usage.get('completion_tokens', 0)}, Total: {usage.get('total_tokens', 0)}")
            
            if hasattr(res, 'tool_calls') and res.tool_calls:
                for tc in res.tool_calls:
                    if 'args' in tc and isinstance(tc['args'], str):
                        tc['args'] = heal_json(tc['args'])
                print(f"  🔧 Calls: {len(res.tool_calls)}")
            else: 
                print("  ✅ Final Answer")
            
            return {
                "messages": delete_msgs + [res],
                "facts": updated_facts,
                "entity_cache": resolved_entities
            }
        except Exception as e:
            error_str = str(e)
            if "413" in error_str:
                return {"messages": [AIMessage(content="Memory full. New chat required.")], "facts": []}
            elif "400" in error_str and attempt < 2:
                print(f"  ⚠️ Syntax Error (Attempt {attempt+1}/3). Retrying...")
                last_error = error_str
                await asyncio.sleep(1)
                continue
            raise e

def extract_entities(obj, resolved_entities: dict):
    """Recursively find entities in tool results."""
    if isinstance(obj, dict):
        # Support basic entity search
        if obj.get("id") and obj.get("name"):
            resolved_entities[obj['id']] = decode_hex_name(obj['name'])
        # Support relation search (relatedEntityLabel)
        elif obj.get("relatedEntityId") and obj.get("relatedEntityLabel"):
            resolved_entities[obj['relatedEntityId']] = decode_hex_name(obj['relatedEntityLabel'])
        for val in obj.values():
            extract_entities(val, resolved_entities)
    elif isinstance(obj, list):
        for item in obj:
            extract_entities(item, resolved_entities)
