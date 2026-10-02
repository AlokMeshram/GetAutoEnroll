import sqlite3
import pandas as pd
from pathlib import Path


# -----------------------------------------
# Database Path
# -----------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = BASE_DIR / "database" / "iac_database.db"


# -----------------------------------------
# Database Manager
# -----------------------------------------

class DatabaseManager:

    def __init__(self):
        self.connection = sqlite3.connect(DB_PATH)

    # -------------------------------------

    def get_state_information(self, state_name):
        """
        Returns complete information about one state.
        """

        query = """
        SELECT

            s.state_name,
            s.urban_pct,
            s.pop_density_per_sq_km,

            e.literacy_rate_pct,
            e.gsdp_current_cr_2022_23,
            e.gsdp_growth_current_pct_2022_23,
            e.unemp_rate_2023_24,

            y.youth_pct_of_population,

            st.pmkvy_rate_per_lakh_youth,

            c.cluster_label

        FROM states s

        JOIN economic_indicators e
            ON s.state_id = e.state_id

        JOIN youth_demographics y
            ON s.state_id = y.state_id

        JOIN skill_training st
            ON s.state_id = st.state_id

        JOIN clusters c
            ON s.state_id = c.state_id

        WHERE s.state_name = ?
        """

        return pd.read_sql(
            query,
            self.connection,
            params=(state_name,)
        )

    # -------------------------------------

    def get_all_states(self):
        """
        Returns list of all state names.
        """

        query = """
        SELECT state_name
        FROM states
        ORDER BY state_name
        """

        cursor = self.connection.cursor()

        cursor.execute(query)

        return cursor.fetchall()

    # -------------------------------------

    def close(self):
        self.connection.close()