import { NextResponse } from "next/server";
import Groq from "groq-sdk";
import { SYSTEM_PROMPT } from "@/lib/prompt";
import { CONFIG } from "@/lib/config";
import { tools, type SearchEntitiesParams, type GetEntityRelationsParams, type GetEntityAttributesParams } from "@/lib/tools";

const groq = new Groq({ apiKey: CONFIG.llmConfig.apiKey });

// Conversation memory
let conversationMemory: Array<any> = [];
// =======================
// GLOBAL ENTITY CACHE
// =======================

const entityCache = new Map<string, any>();


// =======================
// HELPER FUNCTIONS
// =======================

// Decode protobuf hex names
function decodeProtobufName(nameField: string): string {
  try {
    if (typeof nameField === 'string' && nameField.includes('"value"')) {
      const parsed = JSON.parse(nameField);
      const hexValue = parsed.value;

      if (hexValue) {
        const buffer = Buffer.from(hexValue, 'hex');
        return buffer.toString('utf8');
      }
    }
    return nameField;
  } catch (e) {
    return nameField;
  }
}

// Call your API
async function callGraphAPI(method: string, endpoint: string, body?: any) {
  const url = CONFIG.apiUrl + endpoint;

  console.log(`  📡 ${method} ${endpoint}`);
  if (body) {
    console.log(`  📦 Body:`, JSON.stringify(body, null, 2));
  }

  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  const data = await res.json();
  return data;
}

// =======================
// INTERNAL BATCH RESOLVER
// (Not exposed to LLM)
// =======================

async function resolveEntityIds(ids: string[]) {
  const uniqueIds = [...new Set(ids)]
    .filter(id => id && !entityCache.has(id));

  if (uniqueIds.length === 0) return;

  console.log(`  🚀 Batch resolving ${uniqueIds.length} entities`);

  // If you DON'T have a batch endpoint yet,
  // fall back to parallel calls (still fast)
  await Promise.all(
    uniqueIds.map(async (id) => {
      try {
        const result = await callGraphAPI(
          'POST',
          '/v1/entities/search',
          { id }
        );

        const entity = result.body?.[0];
        if (entity) {
          entity.decodedName = decodeProtobufName(entity.name);
          entityCache.set(id, entity);
        }
      } catch {
        console.log(`  ⚠️ Failed to resolve ${id}`);
      }
    })
  );
}


// =======================
// TOOL EXECUTION HANDLERS
// =======================

async function executeSearchEntities(params: SearchEntitiesParams) {
  console.log(`\n[Tool: search_entities]`);
  console.log(`  Params:`, JSON.stringify(params, null, 2));

  // 🔒 Fast-path: ID lookup from cache
  if (params.id && entityCache.has(params.id)) {
    console.log(`  ♻️ Cache hit for ${params.id}`);
    return {
      entities: [entityCache.get(params.id)],
      count: 1
    };
  }

  const result = await callGraphAPI('POST', '/v1/entities/search', params);

  if (!result.body || result.body.length === 0) {
    console.log(`  ⚠️ Search returned 0 results`);
    return { entities: [], count: 0 };
  }

  // Decode + cache
  result.body = result.body.map((entity: any) => {
    if (entity.name) {
      entity.decodedName = decodeProtobufName(entity.name);
    }
    if (entity.id) {
      entityCache.set(entity.id, entity);
    }
    return entity;
  });

  console.log(`  ✅ Found ${result.body.length} entity(ies)`);

  return {
    entities: result.body,
    count: result.body.length
  };
}


async function executeGetEntityRelations(params: GetEntityRelationsParams) {
  console.log(`\n[Tool: get_entity_relations]`);
  console.log(`  Params:`, JSON.stringify(params, null, 2));

  const { entityId, relationshipName, ...bodyParams } = params;

  const body: any = {};
  if (relationshipName) body.name = relationshipName;
  Object.assign(body, bodyParams);

  const endpoint = `/v1/entities/${entityId}/relations`;
  const relations = await callGraphAPI('POST', endpoint, Object.keys(body).length > 0 ? body : undefined);

  // Relations endpoint returns array directly, not wrapped in { body: [...] }
  const relationArray = Array.isArray(relations) ? relations : [];

  console.log(`  ✅ Found ${relationArray.length} relation(s)`);

  // Decode names and fetch missing names
  // =======================
  // Batch resolve related entities
  // =======================

  const relatedIds = relationArray
    .map(r => r.relatedEntityId)
    .filter(Boolean);

  await resolveEntityIds(relatedIds);

  // Attach resolved names
  for (const relation of relationArray) {
    const entity = entityCache.get(relation.relatedEntityId);
    if (entity) {
      relation.relatedEntityName = entity.decodedName;
    }
  }

  return {
    relations: relationArray,
    count: relationArray.length
  };
}

async function executeGetEntityAttributes(params: GetEntityAttributesParams) {
  console.log(`\n[Tool: get_entity_attributes]`);
  console.log(`  Params:`, JSON.stringify(params, null, 2));

  const { categoryId, datasetName } = params;
  const endpoint = `/v1/entities/${categoryId}/attributes/${datasetName}`;

  const result = await callGraphAPI('GET', endpoint);

  console.log(`  ✅ Retrieved attributes`);

  return result;
}

// Execute a tool call
async function executeTool(toolName: string, toolParams: any): Promise<any> {
  try {
    switch (toolName) {
      case 'search_entities':
        return await executeSearchEntities(toolParams as SearchEntitiesParams);

      case 'get_entity_relations':
        return await executeGetEntityRelations(toolParams as GetEntityRelationsParams);

      case 'get_entity_attributes':
        return await executeGetEntityAttributes(toolParams as GetEntityAttributesParams);

      default:
        throw new Error(`Unknown tool: ${toolName}`);
    }
  } catch (error: any) {
    console.error(`  ❌ Tool ${toolName} failed:`, error.message);
    return {
      error: error.message,
      success: false
    };
  }
}

// =======================
// MAIN ROUTE HANDLER
// =======================

export async function POST(req: Request) {
  try {
    const { question } = await req.json();

    if (!question || question.trim() === '') {
      return NextResponse.json({
        success: false,
        error: 'Question is required'
      }, { status: 400 });
    }

    console.log('\n' + '='.repeat(80));
    console.log('QUERY:', question);
    console.log('='.repeat(80));

    // Initialize conversation if empty
    if (conversationMemory.length === 0) {
      conversationMemory.push({
        role: "system",
        content: SYSTEM_PROMPT
      });
    }

    // Add user question
    conversationMemory.push({
      role: "user",
      content: question
    });

    // Function calling loop
    let loopCount = 0;
    const maxLoops = 15; // Allow more loops for complex queries

    while (loopCount < maxLoops) {
      loopCount++;
      console.log(`\n[Loop ${loopCount}] Calling LLM...`);

      const completion = await groq.chat.completions.create({
        model: CONFIG.llmConfig.model,
        messages: conversationMemory,
        tools: tools,
        tool_choice: "auto",
        temperature: 0.1,
      });

      const message = completion.choices[0]?.message;

      if (!message) {
        throw new Error("No message in completion");
      }

      // Add assistant message to conversation
      conversationMemory.push(message);

      // Check if LLM wants to call tools
      if (message.tool_calls && message.tool_calls.length > 0) {
        console.log(`  🔧 LLM requested ${message.tool_calls.length} tool call(s)`);

        // Execute each tool call
        for (const toolCall of message.tool_calls) {
          const toolName = toolCall.function.name;
          const toolParams = JSON.parse(toolCall.function.arguments);

          console.log(`\n  Executing: ${toolName}`);

          const toolResult = await executeTool(toolName, toolParams);

          // Add tool result to conversation
          conversationMemory.push({
            role: "tool",
            tool_call_id: toolCall.id,
            content: JSON.stringify(toolResult)
          });
        }

        // Continue loop to let LLM process tool results
        continue;
      }

      // No tool calls - LLM has provided final answer
      if (message.content) {
        console.log('\n✅ Final answer generated');
        console.log('📝 ANSWER:\n', message.content);
        console.log('\n' + '='.repeat(80));
        console.log('COMPLETE');
        console.log('='.repeat(80) + '\n');

        return NextResponse.json({
          success: true,
          answer: message.content,
          debug: {
            toolCallsUsed: loopCount - 1,
            conversationLength: conversationMemory.length
          }
        });
      }

      // Neither tool calls nor content - something went wrong
      throw new Error("LLM response has neither tool calls nor content");
    }

    // Max loops reached
    throw new Error(`Maximum loop count (${maxLoops}) reached without final answer`);

  } catch (error: any) {
    console.error('\n❌ ERROR:', error.message);
    console.error(error.stack);

    return NextResponse.json({
      success: false,
      error: error.message
    }, { status: 500 });
  }
}



// Clear conversation memory (useful for testing)
export async function DELETE() {
  conversationMemory = [];

  return NextResponse.json({ success: true, message: "Memory cleared" });
}
