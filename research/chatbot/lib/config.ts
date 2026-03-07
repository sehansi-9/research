// lib/config.ts
export const CONFIG = {
  apiUrl: process.env.READ_API_URL,

  entityKinds: [
    { major: "Document", minor: "extgztorg" },
    { major: "Document", minor: "extgztperson" },
    { major: "Person", minor: "citizen" },
    { major: "Organisation", minor: "department" },
    { major: "Organisation", minor: "minister" },
    { major: "Category", minor: "parentCategory" },
    { major: "Dataset", minor: "tabular" }
  ],

  relationshipTypes: [
    "AS_PRESIDENT",
    "AS_MINISTER",
    "AS_DEPARTMENT",
    "AS_APPOINTED",
    "RENAMED_TO",
    "AS_CATEGORY",
    "IS_ATTRIBUTE"
  ],

  specialEntities: {
    governmentRoot: "gov_01"
  },

  llmConfig: {
    apiKey: process.env.GROQ_API_KEY,
    model: "openai/gpt-oss-120b",
    maxTokens: 3000
  }
};
