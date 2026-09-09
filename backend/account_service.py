import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()

MONGODB_DATABASE = os.getenv(
    "MONGODB_DATABASE",
    "university_chatbot"
)

MONGODB_ACCOUNT_COLLECTION = os.getenv(
    "MONGODB_ACCOUNT_COLLECTION",
    "account_data"
)

_client = None
_accounts = None


def _get_accounts_collection():
    global _client
    global _accounts

    if not MONGODB_URI:
        raise RuntimeError(
            "MONGODB_URI is not configured. "
            "Please add MONGODB_URI to your .env file."
        )

    if _accounts is None:
        try:
            _client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
            )

            # Test the connection
            _client.admin.command("ping")

            _accounts = _client[
                MONGODB_DATABASE
            ][
                MONGODB_ACCOUNT_COLLECTION
            ]

            # Create unique email index only after successful connection
            _accounts.create_index(
                "email",
                unique=True
            )

            print("MongoDB connected successfully.")

        except ServerSelectionTimeoutError as e:
            print("MongoDB connection failed.")
            print(e)

            raise RuntimeError(
                "Could not connect to MongoDB Atlas. "
                "Check MongoDB Atlas Network Access and MONGODB_URI."
            )

    return _accounts


def _public_account(account):
    return {
        "id": str(account["_id"]),
        "name": account["name"],
        "email": account["email"],
    }


def create_account(name, email, password):
    collection = _get_accounts_collection()

    name = name.strip()
    email = email.strip().lower()

    if not name:
        raise ValueError("Name is required.")

    if not email:
        raise ValueError("Email is required.")

    if not password:
        raise ValueError("Password is required.")

    password_hash = generate_password_hash(password)

    try:
        result = collection.insert_one({
            "name": name,
            "email": email,
            "password_hash": password_hash,
        })

    except DuplicateKeyError:
        raise ValueError(
            "An account with this email already exists."
        )

    account = collection.find_one({
        "_id": result.inserted_id
    })

    return _public_account(account)


def authenticate_account(email, password):
    collection = _get_accounts_collection()

    email = email.strip().lower()

    account = collection.find_one({
        "email": email
    })

    if not account:
        return None

    if not check_password_hash(
        account["password_hash"],
        password
    ):
        return None

    return _public_account(account)