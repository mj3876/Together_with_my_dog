from pathlib import Path
from Together_with_my_dog_cityselection.fetch_pet_tourapi import PetClient, DEFAULT_BASE_URL
from Together_with_my_dog_cityselection.fetch_tourapi import load_key


def pet_detail(content_id, key_file, operation="detailPetTour2"):
    key = load_key(key_file=Path(key_file))
    client = PetClient(key, DEFAULT_BASE_URL, operation, timeout=20, retries=0)
    payload, parsed = client.request({"MobileOS": "ETC", "MobileApp": "TogetherWithMyDog",
                                      "_type": "json", "contentId": content_id, "pageNo": 1, "numOfRows": 100})
    return payload, parsed[0]
