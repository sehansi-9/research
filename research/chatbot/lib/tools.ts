// lib/tools.ts
import { CONFIG } from "./config";

/**
 * Tool definitions for LLM function calling
 * These define the API operations the LLM can invoke
 */

export const tools = [
    {
        type: "function" as const,
        function: {
            name: "search_entities",
            description: `Search for entities in the temporal graph database. Use this to find entities by name, kind, ID, or other criteria. Returns an array of matching entities with their properties.`,
            parameters: {
                type: "object",
                properties: {
                    id: {
                        type: "string",
                        description: "Entity ID to search for. Can be a single ID or used with other filters."
                    },
                    kind: {
                        type: "object",
                        description: "Entity type to filter by",
                        properties: {
                            major: {
                                type: "string",
                                description: `Major entity category. A REQUIRED FIELD. Available: ${[...new Set(CONFIG.entityKinds.map(k => k.major))].join(', ')}`
                            },
                            minor: {
                                type: "string",
                                description: `Minor entity type. Available: ${CONFIG.entityKinds.map(k => `${k.major}.${k.minor}`).join(', ')}`
                            }
                        }
                    },
                    name: {
                        type: "string",
                        description: "Entity name to search for (partial match supported)"
                    },
                    created: {
                        type: "string",
                        description: "ISO date string for when entity was created"
                    },
                    terminated: {
                        type: "string",
                        description: "ISO date string for when entity was terminated (null means still active)"
                    }
                },
                additionalProperties: false
            }
        }
    },
    {
        type: "function" as const,
        function: {
            name: "get_entity_relations",
            description: `Get relationships for a specific entity. Returns an array of relations with temporal information (startTime, endTime). Use this to traverse the graph and find connected entities. IMPORTANT: This returns an ARRAY directly, not wrapped in a body field.`,
            parameters: {
                type: "object",
                properties: {
                    entityId: {
                        type: "string",
                        description: "The ID of the entity to get relations for"
                    },
                    relationshipName: {
                        type: "string",
                        description: `Type of relationship to filter by. Available: ${CONFIG.relationshipTypes.join(', ')}. Leave empty to get all relations.`
                    },
                    relatedEntityId: {
                        type: "string",
                        description: "Filter by the ID of the related entity"
                    },
                    activeAt: {
                        type: "string",
                        description: "ISO date string - get relations active at this point in time"
                    },
                    startTime: {
                        type: "string",
                        description: "ISO date string - filter by relation start time"
                    },
                    endTime: {
                        type: "string",
                        description: "ISO date string - filter by relation end time (null means ongoing)"
                    },
                    direction: {
                        type: "string",
                        enum: ["incoming", "outgoing"],
                        description: "Direction of relationships to retrieve"
                    }
                },
                required: ["entityId"],
                additionalProperties: false
            }
        }
    },
    {
        type: "function" as const,
        function: {
            name: "get_entity_attributes",
            description: "Get specific attribute for an entity by attribute name code",
            parameters: {
                type: "object",
                properties: {
                    categoryId: {
                        type: "string",
                        description: "The ID of the immediate parent entity"
                    },
                    datasetName: {
                        type: "string",
                        description: "The name of the dataset"
                    }
                },
                required: ["categoryId", "datasetName"],
                additionalProperties: false
            }
        }
    }
];

// Type definitions for tool parameters
export interface SearchEntitiesParams {
    id?: string;
    kind?: {
        major?: string;
        minor?: string;
    };
    name?: string;
    created?: string;
    terminated?: string;
}

export interface GetEntityRelationsParams {
    entityId: string;
    relationshipName?: string;
    relatedEntityId?: string;
    activeAt?: string;
    startTime?: string;
    endTime?: string;
    direction?: "incoming" | "outgoing";
}

export interface GetEntityAttributesParams {
    categoryId: string;
    datasetName: string;
}

export type ToolParams =
    | SearchEntitiesParams
    | GetEntityRelationsParams
    | GetEntityAttributesParams
