from config import OWNER_ID

def its_me(user_id: int) -> bool:
    return user_id == OWNER_ID
