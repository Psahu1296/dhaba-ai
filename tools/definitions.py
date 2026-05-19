# Each tool definition tells the LLM:
# - name: what to call it
# - description: WHEN to use it (LLM reads this to decide)
# - parameters: what arguments to pass

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_top_dishes",
            "description": "Get the most frequently ordered dishes from the dhaba. Use when asked about popular dishes, best sellers, or what sells most.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "How many dishes to return. Default 5.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_kpis",
            "description": "Get today's business KPIs — total revenue, order count, customer count. Use when asked about today's performance, earnings, or business summary.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "get_orders",
            "description": "Get orders from the dhaba. Use when asked about recent orders, order history, pending orders, or orders by date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Filter by date in YYYY-MM-DD format. Example: '2024-01-15'",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by order status. Example: 'pending', 'completed'",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expenses",
            "description": "Get expense records for the dhaba. Use when asked about spending, costs, or expenses for a time period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format.",
                    },
                    "to_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_balance",
            "description": "Get a customer's outstanding balance from the ledger. Use when asked about a specific customer's dues, credit, or balance. Requires phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Customer's phone number.",
                    }
                },
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue",
            "description": "Get revenue/earnings for a time period. Use when asked about revenue, income, or earnings. Period can be 'today', 'weekly', or 'monthly'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period. Must be exactly one of: 'day', 'week', 'month', or 'year'.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_dishes",
            "description": "Semantic search over the full dish menu. Use when asked about specific types of dishes, dietary preferences, price range, or any menu-related question. Better than get_top_dishes for menu exploration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query. Example: 'veg dishes under 50 rupees' or 'spicy non-veg curries'",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return. Default 4.",
                    },
                },
                "required": ["query"],
            },
        },
    },

]
