from core.storage import get_storage

if __name__ == "__main__":
    get_storage().ensure_public_bucket()
    print("Public object reading enabled; anonymous upload/delete/list not granted.")
