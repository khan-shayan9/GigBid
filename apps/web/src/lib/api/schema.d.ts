// Generated from apps/web/openapi.json by `make api-client`. Never edit by hand.
export interface paths {
    "/analytics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Analytics */
        get: operations["analytics_analytics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Session */
        get: operations["session_auth_session_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Inbox */
        get: operations["inbox_jobs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/jobs/{job_id}/analyse": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Analyse */
        post: operations["analyse_jobs__job_id__analyse_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/jobs/{job_id}/skip": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Skip */
        post: operations["skip_jobs__job_id__skip_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/memory": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Memories */
        get: operations["memories_memory_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/memory/{kind}/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Forget */
        delete: operations["forget_memory__kind___item_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Threads */
        get: operations["threads_messages_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/messages/{message_id}/reply": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Draft Reply */
        post: operations["draft_reply_messages__message_id__reply_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/pipeline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Pipeline */
        get: operations["pipeline_pipeline_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Profile */
        get: operations["get_profile_profile_get"];
        /** Save Profile */
        put: operations["save_profile_profile_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/profile/connections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Connections */
        get: operations["connections_profile_connections_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/profile/portfolio": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload Portfolio */
        post: operations["upload_portfolio_profile_portfolio_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Runs */
        get: operations["list_runs_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{thread_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["get_run_runs__thread_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{thread_id}/regenerate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Regenerate */
        post: operations["regenerate_runs__thread_id__regenerate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{thread_id}/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resume */
        post: operations["resume_runs__thread_id__resume_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{thread_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry */
        post: operations["retry_runs__thread_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/runs/{thread_id}/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stream Run */
        get: operations["stream_run_runs__thread_id__stream_get"];
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
        /** Analytics */
        Analytics: {
            /** Approvals */
            approvals: {
                [key: string]: number;
            };
            /** Connects Spent */
            connects_spent: number;
            /**
             * Cost And Latency
             * @description why cost and latency are not shown yet
             */
            cost_and_latency: string;
            /** Decisions */
            decisions: {
                [key: string]: number;
            };
            /** Jobs Analysed */
            jobs_analysed: number;
            /** Needs Attention */
            needs_attention: number;
            /** Outcomes */
            outcomes: {
                [key: string]: number;
            };
            /** Rates By Category */
            rates_by_category: components["schemas"]["RateRow"][];
            /** Top Rejection Reasons */
            top_rejection_reasons: components["schemas"]["ReasonCount"][];
        };
        /** Bid */
        Bid: {
            /** Amount Usd */
            amount_usd: number;
            /**
             * Type
             * @enum {string}
             */
            type: "fixed" | "hourly";
        };
        /** BidDecision */
        BidDecision: {
            /**
             * Decision
             * @enum {string}
             */
            decision: "bid" | "watch" | "skip";
            /** Reasons */
            reasons?: string[];
        };
        /** Body_upload_portfolio_profile_portfolio_post */
        Body_upload_portfolio_profile_portfolio_post: {
            /** File */
            file: string;
        };
        /** ClaimVerdict */
        ClaimVerdict: {
            /** Claim */
            claim: string;
            /**
             * Evidence Ids
             * @default []
             */
            evidence_ids: string[];
            /**
             * Label
             * @enum {string}
             */
            label: "supported" | "partly_supported" | "unsupported";
            /**
             * Reason
             * @default
             */
            reason: string;
            /** Sentence */
            sentence: number;
        };
        /** ComplianceVerdict */
        ComplianceVerdict: {
            /** Allowed */
            allowed: boolean;
            /** Violations */
            violations?: string[];
        };
        /** Connections */
        Connections: {
            /** Connects Balance */
            connects_balance?: number | null;
            /** Marketplace */
            marketplace: boolean;
            /** Marketplace Mode */
            marketplace_mode: string;
            /** Upwork Connected */
            upwork_connected: boolean;
        };
        /** Critique */
        Critique: {
            /** Passed */
            passed: boolean;
            /** Reasons */
            reasons?: string[];
        };
        /** EvidenceItem */
        EvidenceItem: {
            /** Id */
            id: string;
            /** Score */
            score?: number | null;
            /** Text */
            text: string;
            /** Title */
            title: string;
            /** Type */
            type: string;
        };
        /** FitReport */
        FitReport: {
            /** Evidence Ids */
            evidence_ids?: string[];
            /** Matched Skills */
            matched_skills?: string[];
            /** Matrix */
            matrix?: components["schemas"]["RequirementMatch"][];
            /** Missing Skills */
            missing_skills?: string[];
            /** Score */
            score: number;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HourlyRange */
        HourlyRange: {
            /** Max */
            max?: number | null;
            /** Min */
            min?: number | null;
        };
        /** Inbox */
        Inbox: {
            /** Items */
            items: components["schemas"]["InboxItem"][];
        };
        /** InboxItem */
        InboxItem: {
            job: components["schemas"]["Job"];
            run?: components["schemas"]["RunSummary"] | null;
        };
        /** Job */
        Job: {
            /** Applicants */
            applicants?: string | null;
            /** Budget Usd */
            budget_usd?: number | null;
            /** Client Id */
            client_id: string;
            /** Connects Cost */
            connects_cost?: number | null;
            /** Description */
            description: string;
            /** Duration */
            duration?: string | null;
            /** Experience Level */
            experience_level?: string | null;
            hourly_usd?: components["schemas"]["HourlyRange"] | null;
            /** Job Id */
            job_id: string;
            /**
             * Payment Type
             * @enum {string}
             */
            payment_type: "fixed" | "hourly";
            /**
             * Posted At
             * Format: date-time
             */
            posted_at: string;
            /**
             * Skills
             * @default []
             */
            skills: string[];
            /** Title */
            title: string;
        };
        /** JobSpec */
        JobSpec: {
            /** Budget Max */
            budget_max?: number | null;
            /** Budget Min */
            budget_min?: number | null;
            /** Deliverables */
            deliverables?: string[];
            /** Job Id */
            job_id: string;
            /** Required Skills */
            required_skills?: string[];
            /** Title */
            title: string;
        };
        /** LoginIn */
        LoginIn: {
            /** Password */
            password: string;
            /** Username */
            username: string;
        };
        /** MemoryItem */
        MemoryItem: {
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "style" | "outcome";
            /** Summary */
            summary: string;
        };
        /** MemoryList */
        MemoryList: {
            /** Items */
            items: components["schemas"]["MemoryItem"][];
        };
        /** Message */
        Message: {
            /** Client Id */
            client_id: string;
            /**
             * Dry Run
             * @default false
             */
            dry_run: boolean;
            /** Job Id */
            job_id: string;
            /** Message Id */
            message_id: string;
            /**
             * Sender
             * @enum {string}
             */
            sender: "client" | "freelancer";
            /**
             * Sent At
             * Format: date-time
             */
            sent_at: string;
            /** Text */
            text: string;
            /** Thread Id */
            thread_id: string;
        };
        /** MessageThread */
        MessageThread: {
            /** Job Id */
            job_id: string;
            /** Latest Client Message Id */
            latest_client_message_id?: string | null;
            /** Messages */
            messages: components["schemas"]["Message"][];
            reply_run?: components["schemas"]["RunSummary"] | null;
            /** Thread Id */
            thread_id: string;
        };
        /** MessageThreads */
        MessageThreads: {
            /** Threads */
            threads: components["schemas"]["MessageThread"][];
        };
        /** Pipeline */
        Pipeline: {
            /** Cards */
            cards: components["schemas"]["PipelineCard"][];
        };
        /** PipelineCard */
        PipelineCard: {
            /** Job Id */
            job_id: string;
            proposal?: components["schemas"]["Proposal"] | null;
            /**
             * Stage
             * @enum {string}
             */
            stage: "awaiting_approval" | "drafted" | "submitted" | "viewed" | "replied" | "interview" | "hired" | "lost";
            /** Thread Id */
            thread_id?: string | null;
            /** Title */
            title: string;
        };
        /**
         * Preview
         * @description The marketplace's dry run: what will be sent and what it costs. Nothing was spent.
         */
        Preview: {
            proposal?: components["schemas"]["Proposal"] | null;
            /** Unavailable */
            unavailable?: string | null;
        };
        /** PriceQuote */
        PriceQuote: {
            /** Amount Usd */
            amount_usd: number;
            /**
             * Bid Type
             * @enum {string}
             */
            bid_type: "fixed" | "hourly";
            /** Rationale */
            rationale: string;
        };
        /**
         * Profile
         * @description One account's onboarding answers and settings.
         */
        Profile: {
            /** Account */
            account: string;
            /**
             * Autonomy
             * @default manual
             * @enum {string}
             */
            autonomy: "manual" | "auto_skip_low_fit";
            /**
             * Hourly Floor Usd
             * @default 30
             */
            hourly_floor_usd: number;
            /**
             * Persona
             * @description the GigSim user and portfolio this account uses
             */
            persona?: string | null;
            /**
             * Saved Searches
             * @default []
             */
            saved_searches: string[];
            /**
             * Weekly Connects Budget
             * @default 60
             */
            weekly_connects_budget: number;
        };
        /** ProfileIn */
        ProfileIn: {
            /**
             * Autonomy
             * @default manual
             * @enum {string}
             */
            autonomy: "manual" | "auto_skip_low_fit";
            /**
             * Hourly Floor Usd
             * @default 30
             */
            hourly_floor_usd: number;
            /** Persona */
            persona?: string | null;
            /**
             * Saved Searches
             * @default []
             */
            saved_searches: string[];
            /**
             * Weekly Connects Budget
             * @default 60
             */
            weekly_connects_budget: number;
        };
        /** Proposal */
        Proposal: {
            bid: components["schemas"]["Bid"];
            /** Connects Cost */
            connects_cost: number;
            /** Cover Letter */
            cover_letter: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Dry Run
             * @description True: a preview; nothing was stored or sent
             * @default false
             */
            dry_run: boolean;
            /** Job Id */
            job_id: string;
            /** Proposal Id */
            proposal_id: string;
            /** Screening Answers */
            screening_answers: string[];
            /** Status */
            status: string;
        };
        /** ProposalDraft */
        ProposalDraft: {
            /** Cover Letter */
            cover_letter: string;
            /** Evidence Ids */
            evidence_ids?: string[];
            /** Job Id */
            job_id: string;
            /** Screening Answers */
            screening_answers?: string[];
            /**
             * Status
             * @default pending_review
             */
            status: string;
        };
        /** RateRow */
        RateRow: {
            /** Category */
            category: string;
            /** Hired */
            hired: number;
            /** Replied */
            replied: number;
            /** Submitted */
            submitted: number;
        };
        /** ReasonCount */
        ReasonCount: {
            /** Count */
            count: number;
            /** Reason */
            reason: string;
        };
        /** RegenerateIn */
        RegenerateIn: {
            /** Paragraph */
            paragraph: string;
        };
        /** RegenerateOut */
        RegenerateOut: {
            /** Paragraph */
            paragraph: string;
        };
        /** RequirementMatch */
        RequirementMatch: {
            /**
             * Best Score
             * @default 0
             */
            best_score: number;
            /**
             * Covered
             * @default false
             */
            covered: boolean;
            /** Evidence Ids */
            evidence_ids?: string[];
            /** Requirement */
            requirement: string;
        };
        /** ResumeIn */
        ResumeIn: {
            /**
             * Action
             * @enum {string}
             */
            action: "approve" | "edit" | "reject";
            /** Cover Letter */
            cover_letter?: string | null;
            /** Reason */
            reason?: string | null;
            /** Reply */
            reply?: string | null;
        };
        /** RiskReport */
        RiskReport: {
            /** Explanation */
            explanation: string;
            /** Flags */
            flags?: string[];
            /** Score */
            score: number;
        };
        /** RunDetail */
        RunDetail: {
            /** Approval Status */
            approval_status?: string | null;
            /**
             * Claims
             * @default []
             */
            claims: components["schemas"]["ClaimVerdict"][];
            /** Client Message */
            client_message?: string | null;
            compliance?: components["schemas"]["ComplianceVerdict"] | null;
            critique?: components["schemas"]["Critique"] | null;
            decision?: components["schemas"]["BidDecision"] | null;
            draft?: components["schemas"]["ProposalDraft"] | null;
            /**
             * Errors
             * @default []
             */
            errors: string[];
            /**
             * Evidence
             * @default []
             */
            evidence: components["schemas"]["EvidenceItem"][];
            fit_report?: components["schemas"]["FitReport"] | null;
            /** Intent */
            intent?: string | null;
            job?: components["schemas"]["Job"] | null;
            job_spec?: components["schemas"]["JobSpec"] | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "bid" | "conversation";
            /** Pending Approval */
            pending_approval: boolean;
            preview?: components["schemas"]["Preview"] | null;
            price_quote?: components["schemas"]["PriceQuote"] | null;
            /** Reply */
            reply?: string | null;
            /**
             * Revisions
             * @default 0
             */
            revisions: number;
            risk_report?: components["schemas"]["RiskReport"] | null;
            /** Running */
            running: boolean;
            /** Sent */
            sent?: {
                [key: string]: unknown;
            } | null;
            /**
             * Slots
             * @default []
             */
            slots: components["schemas"]["Slot"][];
            /**
             * Status
             * @description dead_letter or needs_attention when stopped
             */
            status?: string | null;
            /**
             * Steps
             * @default 0
             */
            steps: number;
            submission?: components["schemas"]["SubmitResult"] | null;
            /** Thread Id */
            thread_id: string;
            /**
             * Timeline
             * @default []
             */
            timeline: components["schemas"]["TimelineStep"][];
            /**
             * Tokens Used
             * @default 0
             */
            tokens_used: number;
        };
        /** RunList */
        RunList: {
            /** Runs */
            runs: components["schemas"]["RunSummary"][];
        };
        /** RunRef */
        RunRef: {
            /** Thread Id */
            thread_id: string;
        };
        /** RunSummary */
        RunSummary: {
            /** Approval Status */
            approval_status?: string | null;
            /**
             * Category
             * @description the job's first listed skill
             */
            category?: string | null;
            /** Decision */
            decision?: string | null;
            /** Fit Score */
            fit_score?: number | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "bid" | "conversation";
            /** Pending Approval */
            pending_approval: boolean;
            price?: components["schemas"]["PriceQuote"] | null;
            /**
             * Risk Flags
             * @default []
             */
            risk_flags: string[];
            /** Risk Score */
            risk_score?: number | null;
            /** Running */
            running: boolean;
            /** Status */
            status?: string | null;
            /**
             * Subject
             * @description job id or client message id
             */
            subject: string;
            /** Thread Id */
            thread_id: string;
            /** Title */
            title: string;
            /** Updated At */
            updated_at?: string | null;
        };
        /** Session */
        Session: {
            /** Account */
            account: string;
            /** Marketplace Mode */
            marketplace_mode: string;
            /** Personas */
            personas: string[];
            /** Policy Version */
            policy_version: string;
            profile: components["schemas"]["Profile"];
        };
        /** Slot */
        Slot: {
            /** End */
            end: string;
            /** Start */
            start: string;
        };
        /** SubmitResult */
        SubmitResult: {
            /** Balance After */
            balance_after: number;
            /** Connects Cost */
            connects_cost: number;
            /**
             * Dry Run
             * @description True: a preview; no Connects were spent
             * @default false
             */
            dry_run: boolean;
            proposal: components["schemas"]["Proposal"];
        };
        /** TimelineStep */
        TimelineStep: {
            /** At */
            at?: string | null;
            /** Nodes */
            nodes: string[];
            /** Step */
            step: number;
        };
        /** UploadOut */
        UploadOut: {
            /** Bytes */
            bytes: number;
            /** Saved As */
            saved_as: string;
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
    analytics_analytics_get: {
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
                    "application/json": components["schemas"]["Analytics"];
                };
            };
        };
    };
    login_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
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
    logout_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
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
        };
    };
    session_auth_session_get: {
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
                    "application/json": components["schemas"]["Session"];
                };
            };
        };
    };
    health_health_get: {
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
    inbox_jobs_get: {
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
                    "application/json": components["schemas"]["Inbox"];
                };
            };
        };
    };
    analyse_jobs__job_id__analyse_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunRef"];
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
    skip_jobs__job_id__skip_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
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
    memories_memory_get: {
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
                    "application/json": components["schemas"]["MemoryList"];
                };
            };
        };
    };
    forget_memory__kind___item_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kind: string;
                item_id: string;
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
    threads_messages_get: {
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
                    "application/json": components["schemas"]["MessageThreads"];
                };
            };
        };
    };
    draft_reply_messages__message_id__reply_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                message_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunRef"];
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
    pipeline_pipeline_get: {
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
                    "application/json": components["schemas"]["Pipeline"];
                };
            };
        };
    };
    get_profile_profile_get: {
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
                    "application/json": components["schemas"]["Profile"];
                };
            };
        };
    };
    save_profile_profile_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProfileIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Profile"];
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
    connections_profile_connections_get: {
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
                    "application/json": components["schemas"]["Connections"];
                };
            };
        };
    };
    upload_portfolio_profile_portfolio_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_portfolio_profile_portfolio_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadOut"];
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
    list_runs_runs_get: {
        parameters: {
            query?: {
                kind?: "bid" | "conversation";
            };
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
                    "application/json": components["schemas"]["RunList"];
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
    get_run_runs__thread_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                thread_id: string;
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
                    "application/json": components["schemas"]["RunDetail"];
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
    regenerate_runs__thread_id__regenerate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                thread_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegenerateIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RegenerateOut"];
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
    resume_runs__thread_id__resume_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                thread_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResumeIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunRef"];
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
    retry_runs__thread_id__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                thread_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunRef"];
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
    stream_run_runs__thread_id__stream_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                thread_id: string;
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
                    "text/event-stream": unknown;
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
