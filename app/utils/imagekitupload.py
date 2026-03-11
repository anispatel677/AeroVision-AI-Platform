from dotenv import load_dotenv
from imagekitio import ImageKit
import os
load_dotenv()
imagekit = ImageKit(
    private_key=os.getenv("PRIVATE_KEY"),
    # public_key=os.getenv("PUBLIC_KEY"),
    # url_endpoint=os.getenv("URL_ENDPOINT"),
)