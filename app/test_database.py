from utils.database import DatabaseManager

db = DatabaseManager()

state = db.get_state_information("Bihar")

print(state)

db.close()