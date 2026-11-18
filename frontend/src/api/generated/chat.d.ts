// Generated from contracts/openapi.json. Do not edit.
export interface paths {
    "/api/chat": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Chat */
        post: operations["chat_api_chat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/chat/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Chat Stream */
        post: operations["chat_stream_api_chat_stream_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/kb": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Kbs */
        get: operations["list_kbs_api_kb_get"];
        put?: never;
        /** Create Kb */
        post: operations["create_kb_api_kb_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/kb/{kb_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Kb */
        get: operations["get_kb_api_kb__kb_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/kb/{kb_id}/query": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Query */
        post: operations["query_api_kb__kb_id__query_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/kb/{kb_id}/query/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Query Stream */
        post: operations["query_stream_api_kb__kb_id__query_stream_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/models/config": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Model Config */
        get: operations["model_config_api_models_config_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/admin/evals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Evaluate */
        post: operations["evaluate_api_v2_admin_evals_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/admin/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Tools */
        get: operations["tools_api_v2_admin_tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/approvals/{approval_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Decision */
        post: operations["decision_api_v2_approvals__approval_id__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/documents/{doc_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Doc */
        put: operations["update_doc_api_v2_documents__doc_id__put"];
        post?: never;
        /** Delete Doc */
        delete: operations["delete_doc_api_v2_documents__doc_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/documents/{doc_id}/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Doc */
        get: operations["download_doc_api_v2_documents__doc_id__download_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/documents/{doc_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Preview Doc */
        get: operations["preview_doc_api_v2_documents__doc_id__preview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Live */
        get: operations["live_api_v2_health_live_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ready */
        get: operations["ready_api_v2_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/jobs/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Job */
        get: operations["get_job_api_v2_jobs__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/kb": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Kbs */
        get: operations["list_kbs_api_v2_kb_get"];
        put?: never;
        /** Create Kb */
        post: operations["create_kb_api_v2_kb_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/kb/{kb_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Kb */
        get: operations["get_kb_api_v2_kb__kb_id__get"];
        put?: never;
        post?: never;
        /** Delete Kb */
        delete: operations["delete_kb_api_v2_kb__kb_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/kb/{kb_id}/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Docs */
        get: operations["list_docs_api_v2_kb__kb_id__documents_get"];
        put?: never;
        /** Upload */
        post: operations["upload_api_v2_kb__kb_id__documents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/memory": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Memories */
        get: operations["memories_api_v2_memory_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/memory/{memory_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete */
        delete: operations["delete_api_v2_memory__memory_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/memory/consent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Consent */
        put: operations["consent_api_v2_memory_consent_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Models */
        get: operations["models_api_v2_models_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Run */
        post: operations["start_run_api_v2_runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["get_run_api_v2_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/runs/{run_id}/activity": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Activity */
        get: operations["activity_api_v2_runs__run_id__activity_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/runs/{run_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel */
        post: operations["cancel_api_v2_runs__run_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/runs/{run_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Events */
        get: operations["events_api_v2_runs__run_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/runs/{run_id}/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Feedback */
        post: operations["feedback_api_v2_runs__run_id__feedback_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Sessions */
        get: operations["list_sessions_api_v2_sessions_get"];
        put?: never;
        /** Create */
        post: operations["create_api_v2_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Session */
        get: operations["get_session_api_v2_sessions__session_id__get"];
        put?: never;
        post?: never;
        /** Delete Session */
        delete: operations["delete_session_api_v2_sessions__session_id__delete"];
        options?: never;
        head?: never;
        /** Update */
        patch: operations["update_api_v2_sessions__session_id__patch"];
        trace?: never;
    };
    "/api/v2/sessions/{session_id}/messages/{message_id}/regenerate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Regenerate */
        post: operations["regenerate_api_v2_sessions__session_id__messages__message_id__regenerate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sessions/{session_id}/messages/{message_id}/version": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Select Version */
        patch: operations["select_version_api_v2_sessions__session_id__messages__message_id__version_patch"];
        trace?: never;
    };
    "/api/v2/settings/public": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Settings */
        get: operations["settings_api_v2_settings_public_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v2/sources/{evidence_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Source */
        get: operations["source_api_v2_sources__evidence_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActivityData */
        ActivityData: {
            /** Activity Id */
            activity_id?: string | null;
            /** Arguments */
            arguments?: {
                [key: string]: unknown;
            } | null;
            /** Count */
            count?: number | null;
            coverage?: components["schemas"]["SourceCoverage"] | null;
            /**
             * Description
             * @default
             */
            description?: string;
            /** Duration Ms */
            duration_ms?: number | null;
            /** Execution Path */
            execution_path?: ("direct" | "rag" | "agentic") | null;
            /** Goals */
            goals?: string[] | null;
            /** Layer */
            layer?: string | null;
            /** Mode */
            mode?: string | null;
            /** Name */
            name?: string | null;
            /** Origin Run Id */
            origin_run_id?: string | null;
            /** Output */
            output?: {
                [key: string]: unknown;
            } | null;
            /** Parent Id */
            parent_id?: string | null;
            /** Reason Code */
            reason_code?: string | null;
            /** Status */
            status?: string | null;
            /**
             * Title
             * @default
             */
            title?: string;
        } & {
            [key: string]: unknown;
        };
        /** ActivityEvent */
        ActivityEvent: {
            data: components["schemas"]["ActivityData"];
            /** Id */
            id: number;
            /** Run Id */
            run_id: string;
            /** Timestamp */
            timestamp: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "agent_finished" | "agent_started" | "budget" | "cache" | "context" | "escalation" | "generation" | "plan" | "retrieval" | "retrieval_started" | "retry" | "route" | "started" | "tool_denied" | "tool_finished" | "tool_started" | "verification";
        };
        /** AnswerVersion */
        AnswerVersion: {
            /** Created At */
            created_at: string;
            /** Run Id */
            run_id: string;
            /** Status */
            status: string;
        };
        /** Body_create_kb_api_kb_post */
        Body_create_kb_api_kb_post: {
            /**
             * Embedding Model
             * @default demo
             */
            embedding_model?: string;
            /** Files */
            files: Blob[];
            /** Name */
            name: string;
        };
        /** Body_update_doc_api_v2_documents__doc_id__put */
        Body_update_doc_api_v2_documents__doc_id__put: {
            /** File */
            file: Blob;
        };
        /** Body_upload_api_v2_kb__kb_id__documents_post */
        Body_upload_api_v2_kb__kb_id__documents_post: {
            /** Files */
            files: Blob[];
        };
        /** ChatMessage */
        ChatMessage: {
            /**
             * Answer Status
             * @default answered
             * @enum {string}
             */
            answer_status?: "answered" | "clarification" | "insufficient_evidence" | "citation_error" | "indexing" | "no_documents" | "coverage_limit" | "verification_failed";
            /** Content */
            content: string;
            /** Created At */
            created_at: string;
            /** Id */
            id: string;
            /** Parent User Message Id */
            parent_user_message_id?: string | null;
            /** Pending Run Id */
            pending_run_id?: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "user" | "assistant";
            /** Run Id */
            run_id?: string | null;
            /** Sources */
            sources?: components["schemas"]["Citation"][];
            /**
             * Status
             * @default completed
             */
            status?: string;
            /** Versions */
            versions?: components["schemas"]["AnswerVersion"][];
        };
        /** Citation */
        Citation: {
            /**
             * Available
             * @default true
             */
            available?: boolean;
            /** Document Id */
            document_id?: string | null;
            /**
             * Excerpt
             * @default
             */
            excerpt?: string;
            /** Id */
            id: string;
            /**
             * Kind
             * @default document
             * @enum {string}
             */
            kind?: "document" | "tool";
            /** Observed At */
            observed_at?: string | null;
            /** Page */
            page?: number | null;
            /** Section */
            section?: string | null;
            /** Title */
            title: string;
            /** Tool */
            tool?: string | null;
            /** Version */
            version?: number | null;
        };
        /** CompleteData */
        CompleteData: {
            /**
             * Answer
             * @default
             */
            answer?: string;
            /**
             * Answer Status
             * @default answered
             * @enum {string}
             */
            answer_status?: "answered" | "clarification" | "insufficient_evidence" | "citation_error" | "indexing" | "no_documents" | "coverage_limit" | "verification_failed";
            /** Assistant Message Id */
            assistant_message_id?: string | null;
            /** Citations */
            citations?: string[];
            coverage?: components["schemas"]["SourceCoverage"];
            /** Error */
            error?: string | null;
            /**
             * Evidence Count
             * @default 0
             */
            evidence_count?: number;
            /**
             * Execution Path
             * @default direct
             * @enum {string}
             */
            execution_path?: "direct" | "rag" | "agentic";
            /**
             * Grounding
             * @default model
             */
            grounding?: string;
            /** Id */
            id: string;
            /**
             * Latency Ms
             * @default 0
             */
            latency_ms?: number;
            /** Mode */
            mode: string;
            /**
             * Model
             * @default
             */
            model?: string;
            /** Origin Run Id */
            origin_run_id?: string | null;
            /** Regeneration Of Run Id */
            regeneration_of_run_id?: string | null;
            /** Requested Mode */
            requested_mode: string;
            /** Requested Model Id */
            requested_model_id?: string | null;
            /**
             * Route Reason
             * @default
             */
            route_reason?: string;
            /**
             * Served From Cache
             * @default false
             */
            served_from_cache?: boolean;
            /** Session Id */
            session_id?: string | null;
            /** Sources */
            sources?: components["schemas"]["Citation"][];
            /** Status */
            status: string;
            /**
             * Steps
             * @default 0
             */
            steps?: number;
            /**
             * Supported
             * @default false
             */
            supported?: boolean;
            /**
             * Tool Calls
             * @default 0
             */
            tool_calls?: number;
            /** Usage */
            usage?: {
                [key: string]: unknown;
            };
            /** User Message Id */
            user_message_id?: string | null;
        };
        /** CompleteEvent */
        CompleteEvent: {
            data: components["schemas"]["CompleteData"];
            /** Id */
            id: number;
            /** Run Id */
            run_id: string;
            /** Timestamp */
            timestamp: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "complete";
        };
        /** ConsentBody */
        ConsentBody: {
            /** Enabled */
            enabled: boolean;
        };
        /** CreateKb */
        CreateKb: {
            /** Name */
            name: string;
        };
        /** DecisionBody */
        DecisionBody: {
            /** Approved */
            approved: boolean;
        };
        /** DeltaData */
        DeltaData: {
            /** Token */
            token: string;
        };
        /** DeltaEvent */
        DeltaEvent: {
            data: components["schemas"]["DeltaData"];
            /** Id */
            id: number;
            /** Run Id */
            run_id: string;
            /** Timestamp */
            timestamp: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "token";
        };
        /** DocumentPreviewResponse */
        DocumentPreviewResponse: {
            /** Document Id */
            document_id: string;
            /** Next Offset */
            next_offset?: number | null;
            /** Offset */
            offset: number;
            /** Sections */
            sections: components["schemas"]["PreviewSection"][];
            /** Title */
            title: string;
            /** Total Characters */
            total_characters: number;
            /** Version */
            version: number;
        };
        /** DocumentResponse */
        DocumentResponse: {
            /**
             * Can Delete
             * @default false
             */
            can_delete?: boolean;
            /** Content Type */
            content_type: string;
            /** Created At */
            created_at: string;
            /** Id */
            id: string;
            /** Size */
            size: number;
            /** Status */
            status: string;
            /** Title */
            title: string;
            /**
             * Updated At
             * @default
             */
            updated_at?: string;
            /** Version */
            version: number;
        };
        /** ExecutionEnvelope */
        ExecutionEnvelope: components["schemas"]["ActivityEvent"] | components["schemas"]["DeltaEvent"] | components["schemas"]["CompleteEvent"] | components["schemas"]["FailureEvent"];
        /** FailureData */
        FailureData: {
            /** Code */
            code: string;
            /** Correlation Id */
            correlation_id: string;
            /** Message */
            message: string;
            /**
             * Retryable
             * @default true
             */
            retryable?: boolean;
        };
        /** FailureEvent */
        FailureEvent: {
            data: components["schemas"]["FailureData"];
            /** Id */
            id: number;
            /** Run Id */
            run_id: string;
            /** Timestamp */
            timestamp: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "cancelled" | "error";
        };
        /** FeedbackBody */
        FeedbackBody: {
            /** Correction */
            correction?: string | null;
            /** Rating */
            rating: number;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** KnowledgeBaseResponse */
        KnowledgeBaseResponse: {
            /**
             * Can Delete
             * @default false
             */
            can_delete?: boolean;
            /**
             * Created At
             * @default
             */
            created_at?: string;
            /** Documents */
            documents?: components["schemas"]["DocumentResponse"][];
            /** Embedding Model */
            embedding_model: string;
            /** Id */
            id: string;
            /** Name */
            name: string;
        };
        /** LegacyQuery */
        LegacyQuery: {
            /** Model Config Override */
            model_config_override?: {
                [key: string]: unknown;
            } | null;
            /** Question */
            question: string;
        };
        /** PreviewSection */
        PreviewSection: {
            /** Page */
            page?: number | null;
            /** Section */
            section?: string | null;
            /** Text */
            text: string;
        };
        /** RegenerateRequest */
        RegenerateRequest: {
            /** Client Request Id */
            client_request_id: string;
            /** Expected Run Id */
            expected_run_id: string;
        };
        /** RunAccepted */
        RunAccepted: {
            /** Assistant Message Id */
            assistant_message_id?: string | null;
            /** Events Url */
            events_url: string;
            /** Run Id */
            run_id: string;
            /** Status */
            status: string;
            /** User Message Id */
            user_message_id?: string | null;
        };
        /** RunRequest */
        RunRequest: {
            /** Client Message Id */
            client_message_id?: string | null;
            /** Kb Ids */
            kb_ids?: string[];
            /**
             * Mode
             * @default auto
             * @enum {string}
             */
            mode?: "auto" | "direct" | "baseline" | "advanced" | "agentic";
            /** Model Id */
            model_id?: string | null;
            /** Question */
            question: string;
            /** Session Id */
            session_id?: string | null;
        };
        /** RunResponse */
        RunResponse: {
            /**
             * Answer
             * @default
             */
            answer?: string;
            /**
             * Answer Status
             * @default answered
             * @enum {string}
             */
            answer_status?: "answered" | "clarification" | "insufficient_evidence" | "citation_error" | "indexing" | "no_documents" | "coverage_limit" | "verification_failed";
            /** Assistant Message Id */
            assistant_message_id?: string | null;
            /** Citations */
            citations?: string[];
            coverage?: components["schemas"]["SourceCoverage"];
            /** Error */
            error?: string | null;
            /**
             * Evidence Count
             * @default 0
             */
            evidence_count?: number;
            /**
             * Execution Path
             * @default direct
             * @enum {string}
             */
            execution_path?: "direct" | "rag" | "agentic";
            /**
             * Grounding
             * @default model
             */
            grounding?: string;
            /** Id */
            id: string;
            /**
             * Latency Ms
             * @default 0
             */
            latency_ms?: number;
            /** Mode */
            mode: string;
            /**
             * Model
             * @default
             */
            model?: string;
            /** Origin Run Id */
            origin_run_id?: string | null;
            /** Regeneration Of Run Id */
            regeneration_of_run_id?: string | null;
            /** Requested Mode */
            requested_mode: string;
            /** Requested Model Id */
            requested_model_id?: string | null;
            /**
             * Route Reason
             * @default
             */
            route_reason?: string;
            /**
             * Served From Cache
             * @default false
             */
            served_from_cache?: boolean;
            /** Session Id */
            session_id?: string | null;
            /** Sources */
            sources?: components["schemas"]["Citation"][];
            /** Status */
            status: string;
            /**
             * Steps
             * @default 0
             */
            steps?: number;
            /**
             * Tool Calls
             * @default 0
             */
            tool_calls?: number;
            /** Usage */
            usage?: {
                [key: string]: unknown;
            };
            /** User Message Id */
            user_message_id?: string | null;
        };
        /** SelectVersionRequest */
        SelectVersionRequest: {
            /** Expected Run Id */
            expected_run_id: string;
            /** Run Id */
            run_id: string;
        };
        /** SessionRequest */
        SessionRequest: {
            /** Kb Ids */
            kb_ids?: string[];
            /**
             * Title
             * @default New chat
             */
            title?: string;
        };
        /** SessionResponse */
        SessionResponse: {
            /** Active Run Id */
            active_run_id?: string | null;
            /** Id */
            id: string;
            /** Kb Ids */
            kb_ids?: string[];
            /** Messages */
            messages?: components["schemas"]["ChatMessage"][];
            /**
             * Summary
             * @default
             */
            summary?: string;
            /**
             * Summary Status
             * @default idle
             * @enum {string}
             */
            summary_status?: "idle" | "queued" | "running" | "completed" | "failed";
            /** Summary Through */
            summary_through?: string | null;
            /**
             * Title
             * @default New chat
             */
            title?: string;
            /** Updated At */
            updated_at: string;
        };
        /** SessionUpdate */
        SessionUpdate: {
            /** Kb Ids */
            kb_ids?: string[] | null;
            /** Title */
            title?: string | null;
        };
        /** SourceCoverage */
        SourceCoverage: {
            /** Documents */
            documents?: string[];
            /**
             * Read Chunks
             * @default 0
             */
            read_chunks?: number;
            /**
             * Strategy
             * @default none
             * @enum {string}
             */
            strategy?: "none" | "lookup" | "full_document" | "map_reduce" | "partial";
            /**
             * Total Chunks
             * @default 0
             */
            total_chunks?: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    chat_api_chat_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    chat_stream_api_chat_stream_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    list_kbs_api_kb_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_kb_api_kb_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_create_kb_api_kb_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_kb_api_kb__kb_id__get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                kb_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    query_api_kb__kb_id__query_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                kb_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LegacyQuery"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    query_stream_api_kb__kb_id__query_stream_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                kb_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LegacyQuery"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    model_config_api_models_config_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    evaluate_api_v2_admin_evals_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    tools_api_v2_admin_tools_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    decision_api_v2_approvals__approval_id__post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                approval_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DecisionBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: boolean;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_doc_api_v2_documents__doc_id__put: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                doc_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_update_doc_api_v2_documents__doc_id__put"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_doc_api_v2_documents__doc_id__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                doc_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_doc_api_v2_documents__doc_id__download_get: {
        parameters: {
            query?: {
                version?: number | null;
            };
            header?: {
                authorization?: string | null;
            };
            path: {
                doc_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/octet-stream": Blob;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_doc_api_v2_documents__doc_id__preview_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
                version?: number | null;
            };
            header?: {
                authorization?: string | null;
            };
            path: {
                doc_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentPreviewResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    live_api_v2_health_live_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    ready_api_v2_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_job_api_v2_jobs__job_id__get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_kbs_api_v2_kb_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeBaseResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_kb_api_v2_kb_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateKb"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeBaseResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_kb_api_v2_kb__kb_id__get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                kb_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeBaseResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_kb_api_v2_kb__kb_id__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                kb_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_docs_api_v2_kb__kb_id__documents_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                kb_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_api_v2_kb__kb_id__documents_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                kb_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_api_v2_kb__kb_id__documents_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    memories_api_v2_memory_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_api_v2_memory__memory_id__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                memory_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    consent_api_v2_memory_consent_put: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConsentBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: boolean;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    models_api_v2_models_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    start_run_api_v2_runs_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RunRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_run_api_v2_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    activity_api_v2_runs__run_id__activity_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExecutionEnvelope"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_api_v2_runs__run_id__cancel_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    events_api_v2_runs__run_id__events_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
                "Last-Event-ID"?: string | null;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                    "text/event-stream": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    feedback_api_v2_runs__run_id__feedback_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sessions_api_v2_sessions_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_api_v2_sessions_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["SessionRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_session_api_v2_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_session_api_v2_sessions__session_id__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_api_v2_sessions__session_id__patch: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    regenerate_api_v2_sessions__session_id__messages__message_id__regenerate_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                message_id: string;
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegenerateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunAccepted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    select_version_api_v2_sessions__session_id__messages__message_id__version_patch: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                message_id: string;
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SelectVersionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChatMessage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    settings_api_v2_settings_public_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    source_api_v2_sources__evidence_id__get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                evidence_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
