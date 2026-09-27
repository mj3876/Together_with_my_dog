"""Transactional, repeatable service-catalog migration with source lineage."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from app.db.normalized import initialize, open_readonly
from app.schemas.place import Place


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def identity(*parts):
    return hashlib.sha256(encoded(parts).encode()).hexdigest()


def put(conn, table, data, key):
    fields = list(data)
    updates = [f'{f}=excluded.{f}' for f in fields if f != key]
    conn.execute(f'INSERT INTO {table} ({",".join(fields)}) VALUES ({",".join("?" for _ in fields)}) '
                 f'ON CONFLICT({key}) DO UPDATE SET {",".join(updates)}', list(data.values()))


def source_file(conn, path, public_url=None):
    path = Path(path)
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    sid = 'source_' + identity(public_url or path.name)[:24]
    run = 'run_' + identity(sid, digest)[:24]
    fid = 'file_' + identity(run, path.name)[:24]
    conn.execute('INSERT OR IGNORE INTO data_sources VALUES (?,?,?,?,?,?)',
                 (sid, path.name, '공개 조사 자료', 'derived', public_url, '원문/검토 파일의 출처 보존'))
    conn.execute('INSERT OR IGNORE INTO ingestion_runs VALUES (?,?,?,?,?,?)',
                 (run, sid, datetime.now(timezone.utc).isoformat(), 'complete', '{}', 'service catalog import'))
    conn.execute('INSERT OR IGNORE INTO source_files VALUES (?,?,?,?,?,?,?)',
                 (fid, run, path.as_posix(), digest, path.suffix.lstrip('.'), public_url, None))
    return fid


def raw(conn, fid, locator, value, external=None):
    rid = 'raw_' + identity(fid, locator)[:32]
    conn.execute('INSERT OR IGNORE INTO raw_records VALUES (?,?,?,?,?)',
                 (rid, fid, locator, external, encoded(value)))
    return rid


def read_rows(conn, path):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, list):
        raise ValueError(f'{path.name}: JSON 배열이 필요합니다.')
    fid = source_file(conn, path)
    return [(r, raw(conn, fid, f'/{i}', r, r.get('id') or r.get('venue_id'))) for i, r in enumerate(data)]


def save_venue(conn, p, record):
    previous = conn.execute('SELECT latitude,longitude,official_url,review_status,location_record_id FROM venues WHERE venue_id=?', (p['venue_id'],)).fetchone()
    lat, lon = p.get('latitude'), p.get('longitude')
    location_record = record
    if lat is None and previous:
        lat, lon = previous[:2]
        location_record = previous[4]
    if previous and previous[3] == 'reviewed' and not p.get('active'):
        return
    put(conn, 'venues', dict(venue_id=p['venue_id'], name=p['name'], address=p['address'],
        latitude=lat, longitude=lon, official_url=p.get('official_url') or (previous[2] if previous else None),
        location_record_id=location_record, review_status='reviewed' if p.get('active') else 'pending'), 'venue_id')


def save_place(conn, data, record, review=None, approved=False):
    p = Place.model_validate(data)
    if p.is_demo:
        raise ValueError(f'{p.id}: 데모 자료는 이전할 수 없습니다.')
    policy = p.policy
    if approved:
        if not (p.active and policy.verified and policy.pet_allowed):
            raise ValueError(f'{p.id}: 승인 자료의 활성/검증/허용 상태를 확인하세요.')
        if not policy.checked_at or policy.checked_at > date.today():
            raise ValueError(f'{p.id}: 확인일 오류')
        if not (policy.max_dogs or policy.dogs_unlimited) or not (policy.max_weight_kg or policy.weight_unlimited):
            raise ValueError(f'{p.id}: 마릿수/체중 제한 미확인')
        if not p.address.startswith(('대전 ', '대전광역시 ')) or not (36.1 < p.latitude < 36.55 and 127.2 < p.longitude < 127.65):
            raise ValueError(f'{p.id}: 대전 위치 확인 필요')
        if p.category == 'restaurant' and not p.serves_meals:
            raise ValueError(f'{p.id}: 식사 메뉴 미확인')
        if p.category in {'lodging', 'activity'} and not p.product_name:
            raise ValueError(f'{p.id}: 상품명 미확인')
        if p.category == 'activity' and (not p.recurring or not p.duration_minutes):
            raise ValueError(f'{p.id}: 체험 운영/소요시간 미확인')
    prior = conn.execute('SELECT review_status,checked_at FROM pet_policy_versions WHERE offering_id=? AND is_current=1', (p.id,)).fetchone()
    # Old inactive snapshots must not silently demote a verified product.
    if prior and prior[0] == 'verified' and not approved:
        return
    if prior and approved and policy.checked_at and prior[1] > policy.checked_at.isoformat():
        raise ValueError(f'{p.id}: 현재 규정보다 오래된 승인 자료')
    save_venue(conn, p.model_dump(mode='json'), record)
    scope = (review or {}).get('scope_type') or {'lodging':'room','restaurant':'space','activity':'program'}[p.category]
    put(conn, 'offerings', dict(offering_id=p.id, venue_id=p.venue_id, name=p.product_name or p.name,
        category=p.category, scope_type=scope, participation_mode=p.participation_mode,
        serves_meals=int(p.serves_meals), recurring=int(p.recurring), duration_minutes=p.duration_minutes,
        checkin_minute=p.checkin_minute, checkout_minute=p.checkout_minute, enabled=int(p.active),
        evidence_record_id=record, note=''), 'offering_id')
    put(conn, 'offering_details', dict(offering_id=p.id, description=p.description, product_name=p.product_name,
        schedule_note=p.schedule_note, price_note=p.price_note,
        source_url=str(policy.source_url) if policy.source_url else None, source_quote=policy.source_quote,
        opens_minute=p.opens_minute, closes_minute=p.closes_minute), 'offering_id')
    values = dict(offering_id=p.id, checked_at=policy.checked_at.isoformat() if policy.checked_at else '',
        review_status='verified' if policy.verified else (review or {}).get('review_status', 'pending'),
        pet_allowed=(review or {}).get('pet_allowed', policy.pet_allowed if policy.verified or policy.pet_allowed else None),
        dogs_limit_state='unlimited' if policy.dogs_unlimited else 'limited' if policy.max_dogs else 'unknown',
        max_dogs=policy.max_dogs,
        weight_limit_state='unlimited' if policy.weight_unlimited else 'limited' if policy.max_weight_kg else 'unknown',
        max_weight_kg=policy.max_weight_kg,
        weight_operator=policy.weight_operator if policy.max_weight_kg else None,
        note=policy.source_quote)
    pid = 'policy_' + identity(values, policy.requirements)[:32]
    conn.execute('UPDATE pet_policy_versions SET is_current=0 WHERE offering_id=? AND policy_id<>?', (p.id, pid))
    put(conn, 'pet_policy_versions', dict(policy_id=pid, **values, is_current=1), 'policy_id')
    # This record is the reviewed declaration; original evidence files are preserved separately.
    conn.execute('INSERT OR IGNORE INTO policy_evidence VALUES (?,?,?,?)',
                 (pid, record, 'review_declaration', policy.source_quote or '미검증 후보'))
    for index, requirement in enumerate(policy.requirements):
        cid = 'condition_' + identity(pid, index, requirement)[:32]
        put(conn, 'policy_conditions', dict(condition_id=cid, policy_id=pid, condition_type='other',
            operator='required', value_json=encoded(requirement), enforcement='manual',
            summary=requirement, evidence_record_id=record), 'condition_id')
    for pending in (review or {}).get('pending', []):
        issue = 'issue_' + identity(p.id, pending)[:32]
        conn.execute('INSERT OR IGNORE INTO review_issues VALUES (?,?,?,?,?,?,?,?,?)',
                     (issue, p.venue_id, p.id, record, 'review', pending, 'open',
                      (review or {}).get('checked_at', ''), None))
    if approved:
        # Approval does not resolve unrelated venue, schedule or manual-condition issues.
        conn.execute("UPDATE review_issues SET status='resolved',resolution_record_id=? WHERE offering_id=? AND field_name='review' AND status='open'", (record,p.id))


def migrate(source_db, review_dir, target_db, approved=None, dry_run=False):
    target = Path(target_db).resolve()
    if target == Path(source_db).resolve():
        raise ValueError('원본 DB와 대상 DB는 달라야 합니다.')
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(':memory:' if dry_run else target)
    try:
        if dry_run and target.exists():
            with open_readonly(target) as existing:
                existing.backup(conn)
        initialize(conn)
        with conn:
            reviewed = {}
            source_records = {}
            review_path = Path(review_dir)
            for row, rid in read_rows(conn, review_path / 'policy_review.json'):
                reviewed[row['id']] = (row, rid)
            # Keep original evidence hashes as well as the derived review JSON.
            for item, manifest_record in read_rows(conn, review_path/'sources.json'):
                source_records.setdefault(item.get('url'), []).append(manifest_record)
                if 'file' not in item:
                    continue  # Metadata explicitly records that no local original was archived.
                evidence = review_path / item['file']
                if not evidence.is_file():
                    raise ValueError(f'근거 파일 누락: {item["file"]}')
                if hashlib.sha256(evidence.read_bytes()).hexdigest() != item['sha256']:
                    raise ValueError(f'근거 해시 불일치: {item["file"]}')
                source_file(conn, evidence, item.get('url'))
            with open_readonly(source_db) as source:
                rows = [json.loads(r[0]) for r in source.execute('SELECT document FROM places ORDER BY id')]
            fid = source_file(conn, source_db)
            for i, row in enumerate(rows):
                rid = raw(conn, fid, f'/places/{row["id"]}', row, row['id'])
                if row['id'] not in reviewed or row.get('policy', {}).get('verified'):
                    save_place(conn, row, rid)
            for row, rid in read_rows(conn, review_path/'places_import_inactive.json'):
                review, review_record = reviewed.get(row['id'], ({}, rid))
                save_place(conn, row, review_record, review)
            for row, rid in read_rows(conn, review_path/'restaurant_candidates.json'):
                save_venue(conn, row, rid)
                oid = row['venue_id'] + '_meal'
                if not conn.execute('SELECT 1 FROM offerings WHERE offering_id=?', (oid,)).fetchone():
                    put(conn,'offerings',dict(offering_id=oid, venue_id=row['venue_id'],name=row['name'],
                        category='restaurant',scope_type='unresolved',enabled=0,evidence_record_id=rid),'offering_id')
                if not conn.execute('SELECT 1 FROM pet_policy_versions WHERE offering_id=? AND is_current=1',(oid,)).fetchone():
                    pid='registry_'+identity(oid,row.get('checked_at'))[:32]
                    put(conn,'pet_policy_versions',dict(policy_id=pid,offering_id=oid,checked_at=row.get('checked_at',''),
                        review_status='partial',pet_allowed=int(row['pet_allowed']) if row.get('pet_allowed') is not None else None,
                        note='대전시 반려동물 동반 음식점 등록 자료. 세부 이용 조건 미확인.'),'policy_id')
                    conn.execute('INSERT OR IGNORE INTO policy_evidence VALUES (?,?,?,?)',
                        (pid,rid,'pet_allowed','반려동물 동반 음식점 등록 사실'))
                    put(conn,'offering_details',dict(offering_id=oid,source_url=row.get('source_url'),
                        source_quote='대전시 반려동물 동반 음식점 등록 현황',
                        description='공식 등록 명부의 실제 음식점 후보. 식사 메뉴·동반 공간의 세부 조건은 미확인.',
                        schedule_note='방문일 영업시간과 동반 공간을 확인해 주세요.'),'offering_id')
                for pending in row.get('pending', []):
                    conn.execute('INSERT OR IGNORE INTO review_issues VALUES (?,?,?,?,?,?,?,?,?)',
                        ('issue_'+identity(oid,pending)[:32],row['venue_id'],oid,rid,'review',pending,'open',row.get('checked_at',''),None))
            for row, rid in read_rows(conn, review_path/'restaurant_registrations.json'):
                put(conn,'food_registrations',dict(registration_id=row['registration_id'],venue_id=row['venue_id'],
                    source_record_id=rid,registry_as_of=row['registry_as_of'],source_row_number=row['source_row'],
                    licensing_authority_raw=row['authority_raw'],licensing_authority_resolved=row['authority_resolved'],
                    resolution_note='; '.join(row.get('transform_notes',[])) or None,
                    business_type=row['business_type'],source_note=row.get('source_note')),'registration_id')
            if approved:
                approvals = read_rows(conn, approved)
                ids = [r['id'] for r,_ in approvals]
                if len(set(ids)) != len(ids): raise ValueError('승인 자료 중복 ID')
                for row,rid in approvals: save_place(conn,row,rid,approved=True)
            for pid,url in conn.execute('SELECT p.policy_id,d.source_url FROM pet_policy_versions p JOIN offering_details d USING(offering_id) WHERE p.is_current=1').fetchall():
                for rid in source_records.get(url, []):
                    conn.execute('INSERT OR IGNORE INTO policy_evidence VALUES (?,?,?,?)',
                                 (pid,rid,'source_archive','공식 원문 또는 수집 접근 기록 연결'))
            conn.execute('INSERT OR IGNORE INTO data_sources VALUES (?,?,?,?,?,?)',
                         ('tourapi','한국관광공사 TourAPI','한국관광공사','api','https://api.visitkorea.or.kr/','기존 콘텐츠 ID 연결'))
            for vid,rid in conn.execute("SELECT venue_id,location_record_id FROM venues WHERE venue_id GLOB 'tour_[0-9]*'").fetchall():
                conn.execute('INSERT OR IGNORE INTO venue_source_keys VALUES (?,?,?,?)',('tourapi',vid[5:],vid,rid))
            if conn.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('외래키 검사 실패')
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('DB 무결성 검사 실패')
        return dict(dry_run=dry_run, target=str(target), counts={table:conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
            for table in ['venues','offerings','pet_policy_versions','food_registrations','raw_records','review_issues']})
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-db', type=Path, default=Path('data/app.db'))
    parser.add_argument('--review-dir', type=Path, default=Path('outputs/policy_review_20260925'))
    parser.add_argument('--target-db', type=Path, default=Path('data/app_normalized.db'))
    parser.add_argument('--approved', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args=parser.parse_args()
    try:
        print(json.dumps(migrate(args.source_db,args.review_dir,args.target_db,args.approved,args.dry_run),ensure_ascii=False,indent=2))
    except (ValueError,OSError,sqlite3.Error) as exc:
        parser.exit(1, f'이전 실패: {exc}\n')


if __name__ == '__main__': main()
