"""Project 16: the agent tree. Four agents, three tools each; one description per node, used by every variant."""

AGENTS = {
    "research": ("Finds and reads outside information: the web, papers, articles", {
        "web_search": "Search the web for current, public information",
        "read_paper": "Fetch and read a specific research paper by title or id",
        "summarize_url": "Read one given web page and summarize it",
    }),
    "coding": ("Works on the company's own codebase", {
        "run_tests": "Run the test suite and report failures",
        "search_code": "Find where something is defined or used in the codebase",
        "open_pull_request": "Open a pull request from a branch",
    }),
    "finance": ("Money inside the company: invoices, refunds, revenue", {
        "get_invoice": "Fetch an invoice by its id",
        "issue_refund": "Refund a charge to a customer",
        "forecast_revenue": "Forecast future revenue from past figures",
    }),
    "support": ("Helps a customer with their account or an order's status", {
        "lookup_order": "Look up an order's status and delivery",
        "reset_password": "Send the customer a password reset link",
        # Real test, first run: all three variants sent "the reset email never arrives (3 tries)" to reset_password.
        # The description never said WHEN a human takes over; now it does, for every variant alike.
        "create_ticket": "Hand the problem to a human: a self-service step already failed, or it needs judgment "
                         "(damage, complaints, disputes)",
    }),
}
TOOL_AGENT = {tool: agent for agent, (_, tools) in AGENTS.items() for tool in tools}
