import sqlite3

from langchain_core.tools import tool

DB_PATH = "data.db"


def get_db_connection() -> sqlite3.Connection:
    """Creates and returns a database connection."""
    # TODO: This does not go here. Move it in the future
    try:
        conn = sqlite3.connect(DB_PATH)
        return conn
    except sqlite3.Error as e:
        raise Exception(f"Database connection error: {e}")


@tool
def fetch_spending_events(customer_id: int, months: int = None, plan_name: str = None) -> str:
    """
    Fetches spending events for a customer with optional filtering by months or plan.
    Note: customer_id will be auto-filled if customer has been validated.
    Args:
        customer_id: The ID of the customer (will be auto-filled if validation has occurred)
        months: Optional number of most recent months to retrieve
        plan_name: Optional plan name to filter by
    Returns:
        A formatted string with the spending events information
    """
    if not customer_id:
        return "Error: Customer must be validated before accessing spending data."

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM spending_events WHERE customer_id = ?"
        params = [customer_id]

        if plan_name:
            query += " AND plan_name = ?"
            params.append(plan_name)

        if months:
            query += " ORDER BY billing_end DESC LIMIT ?"
            params.append(months)
        else:
            query += " ORDER BY billing_end DESC"

        cursor.execute(query, params)
        results = cursor.fetchall()

        if not results:
            return "No spending events found with the given criteria."

        # Get column names for better formatting
        column_names = [description[0] for description in cursor.description]

        # Format the results
        output = "Spending events:\n"
        for row in results:
            output += "\n"
            for i, value in enumerate(row):
                output += f"{column_names[i]}: {value}\n"
            output += "----------"

        return output

    except sqlite3.Error as e:
        return f"Database error: {e}"
    finally:
        if conn:
            conn.close()


@tool
def list_supported_plans() -> list[str]:
    """
    Returns a list of electricity plans supported by the system.
    Returns:
        A list of plan names
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT plan_name FROM electricity_plans")
        results = cursor.fetchall()

        if not results:
            return ["Standard Plan", "Eco Plan", "Night Plan"]  # Fallback if no DB data

        return [row[0] for row in results]

    except sqlite3.Error:
        # Fallback if database error
        return ["Standard Plan", "Eco Plan", "Night Plan"]
    finally:
        if conn:
            conn.close()


@tool
def fetch_plan_information(plan_name: str) -> str:
    """
    Fetches detailed information about a specific electricity plan.
    Args:
        plan_name: The name of the plan to look up
    Returns:
        A formatted string with plan details
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM electricity_plans WHERE plan_name = ?", (plan_name,))
        result = cursor.fetchone()

        if not result:
            return f"No information found for plan: {plan_name}"

        # Get column names for better formatting
        column_names = [description[0] for description in cursor.description]

        # Format the result
        output = f"Information for {plan_name}:\n\n"
        for i, value in enumerate(result):
            if column_names[i] != "plan_id":  # Skip ID for user-facing output
                output += f"{column_names[i]}: {value}\n"

        return output

    except sqlite3.Error as e:
        return f"Database error: {e}"
    finally:
        if conn:
            conn.close()


@tool
def validate_customer(customer_id: int = None, email: str = None) -> dict:
    """
    Validates if a customer exists by ID or email and returns customer information.
    Args:
        customer_id: The ID of the customer to look up (optional)
        email: The email of the customer to look up (optional)
    Returns:
        A dictionary with validation result and customer info if found
    """
    if customer_id is None and email is None:
        return {
            "valid": False,
            "message": "Either customer_id or email must be provided",
            "customer_id": None,
            "customer_info": None,
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if customer_id is not None:
            cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
        else:
            cursor.execute("SELECT * FROM customers WHERE email = ?", (email,))

        result = cursor.fetchone()

        if not result:
            return {
                "valid": False,
                "message": "No customer found with the provided information",
                "customer_id": None,
                "customer_info": None,
            }

        # Get column names for better formatting
        column_names = [description[0] for description in cursor.description]

        # Create a dictionary with customer info
        customer_info = {}
        for i, value in enumerate(result):
            customer_info[column_names[i]] = value

        return {
            "valid": True,
            "message": "Customer found",
            "customer_id": customer_info["customer_id"],
            "customer_info": customer_info,
        }

    except sqlite3.Error as e:
        return {"valid": False, "message": f"Database error: {e}", "customer_id": None, "customer_info": None}
    finally:
        if conn:
            conn.close()
