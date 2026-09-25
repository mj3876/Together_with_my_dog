import json
from datetime import datetime, timezone
from pathlib import Path
from Together_with_my_dog_cityselection.fetch_pet_tourapi import PetClient, DEFAULT_BASE_URL
from Together_with_my_dog_cityselection.fetch_tourapi import load_key, ApiError

root = Path('tmp/policy_research_20260925/tourapi_details')
key = load_key(key_file=Path('.secrets/pet_tourapi.key'))
for content_id, type_id in [('3533154', '32'), ('2930677', '12')]:
    for operation in ['detailCommon2', 'detailIntro2']:
        client = PetClient(key, DEFAULT_BASE_URL, operation, timeout=20, retries=0)
        params = dict(MobileOS='ETC', MobileApp='TogetherWithMyDog', _type='json',
                      contentId=content_id, pageNo=1, numOfRows=100)
        if operation == 'detailIntro2':
            params['contentTypeId'] = type_id
        try:
            raw, parsed = client.request(params)
        except ApiError as exc:
            print(content_id, operation, str(exc))
            continue
        (root / f'{content_id}_{operation}.json').write_bytes(raw)
        (root / f'{content_id}_{operation}_review.json').write_text(json.dumps(dict(
            content_id=content_id, operation=operation, checked_at=datetime.now(timezone.utc).isoformat(),
            records=parsed[0]), ensure_ascii=False, indent=2), encoding='utf-8')
        print(content_id, operation, len(parsed[0]))
