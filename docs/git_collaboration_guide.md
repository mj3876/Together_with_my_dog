# Together_with_my_dog Git 협업 가이드

Git Bash 기준 · 수정일: 2026-09-20

저장소: [Together_with_my_dog](https://github.com/mj3876/Together_with_my_dog)

**최초 한 번 클론 → 자기 브랜치에서 작업 → add·commit·push → GitHub에서 PR 병합** 순서입니다.

## 1. 최초 한 번: 클론

이미 클론한 현재 PC에서는 건너뜁니다. 새 PC에서는 저장할 상위 폴더에서 실행합니다.

```bash
git clone https://github.com/mj3876/Together_with_my_dog.git
cd Together_with_my_dog
git config user.name "본인 이름"
git config user.email "본인의 GitHub 이메일"
```

두 사람 모두 각자의 GitHub 계정과 저장소 쓰기 권한을 사용합니다.

## 2. 최초 한 번: 자기 브랜치 만들기

`main`은 통합용, `work/person-a`와 `work/person-b`는 각자 작업용입니다. **작업 브랜치 2개 + main = 총 3개**입니다.

현재 `main`에서 아래 중 **본인 명령만** 실행합니다. 현재 PC에서 이미 수정하거나 add한 내용도 새 브랜치에 유지됩니다.

**A:**

```bash
git switch -c work/person-a
git push -u origin work/person-a
```

**B:**

```bash
git switch -c work/person-b
git push -u origin work/person-b
```

이미 만든 브랜치는 다시 만들지 않고 3절부터 진행합니다.

## 3. 매 작업 시작: 최신 내용 받기

항상 저장소 최상위 폴더에서 실행합니다. 현재 PC의 Git Bash 경로는 다음과 같습니다.

```bash
cd /c/Users/ms840/mjuser/Together_with_my_dog
```

아래는 A 기준이며 **B는 person-a를 person-b로 바꿉니다.** 미커밋 작업이 있으면 먼저 4절로 저장한 뒤 동기화합니다.

```bash
git switch work/person-a
git fetch origin
git merge --ff-only origin/work/person-a
git merge --no-edit origin/main
```

내 원격 브랜치와 최신 main의 변경을 가져옵니다. 오류나 충돌이 나면 다음 명령을 진행하지 말고 해결합니다.

## 4. 매 작업 완료: add → commit → push

파일을 저장하고 기능이 정상 동작하는지 확인한 뒤, **저장소 최상위 폴더의 자기 작업 브랜치에서** 실행합니다.

```bash
git add .
git commit -m "feat: 이번 작업 내용"
git push
```

- `add`: 이번 커밋에 포함할 변경 선택.
- `commit`: 내 PC에 변경 기록. 메시지는 실제 작업 내용으로 바꿉니다.
- `push`: GitHub의 내 브랜치에 업로드.

**현재 .gitignore 기준:** 지역선정 Python 스크립트, 서비스 코드, docs 전체, config/requirements.txt, config/.env.example, outputs의 공유 결과물은 포함합니다. data·runs·루트 region_monthly.csv·테스트 코드·인증정보·가상환경·캐시는 제외합니다. 루트 .gitignore는 저장소 전체에 적용되므로 이동하지 않습니다. 이미 Git이 추적하는 파일에는 ignore 규칙이 소급 적용되지 않습니다.

`git add .`은 삭제·이동도 반영합니다. 삭제를 제외하고 새 파일·수정만 추가하려면 대신 `git add --ignore-removal .`을 사용합니다. 단, 이미 add한 삭제는 취소되지 않으며 이동 전 파일을 남기면 GitHub에 구버전과 새 위치의 파일이 둘 다 남습니다.

## 5. GitHub에서 PR 생성·병합

1. [Pull requests](https://github.com/mj3876/Together_with_my_dog/pulls) → New pull request.
2. **base: main / compare: 내 작업 브랜치** 선택.
3. 제목과 본문에 변경 내용·확인한 동작을 짧게 작성하고 상대방에게 리뷰 요청.
4. 상대 리뷰와 필요한 검증이 끝나면 **Create a merge commit**으로 병합.

**두 사람이 지킬 사항:**

- main에 직접 커밋·푸시하지 않습니다.
- 같은 파일을 수정하거나 파일 위치를 옮길 때는 먼저 서로 알립니다.
- 한쪽 PR이 먼저 병합되면 다른 쪽은 **3절 실행 → 동작 확인 → git push** 후 자신의 PR을 병합합니다.
- 열린 PR에 같은 브랜치로 푸시하면 변경이 계속 추가됩니다. 다음 작업은 현재 PR 병합 후 시작합니다.
- 계속 사용할 작업 브랜치는 삭제하지 않습니다. squash 대신 merge commit을 사용합니다. 저장소에서 허용하지 않으면 관리자와 병합 방식을 먼저 맞춥니다.
- 강제 푸시(`--force`)는 사용하지 않습니다.

자기 PR 병합 후에도 **3절을 다시 실행하고 `git push`**하면 다음 작업을 시작할 수 있습니다. 고정 브랜치를 재사용할 때의 병합 방식은 [GitHub 공식 안내](https://docs.github.com/en/pull-requests/reference/pull-request-merges)를 참고합니다.

## 6. 충돌이 생겼을 때만

편집기에서 충돌 파일을 열어 양쪽 변경을 반영하고 `<<<<<<<`, `=======`, `>>>>>>>` 표시를 제거합니다. 동작을 확인한 뒤 실행합니다.

```bash
git add .
git commit -m "merge: 충돌 해결"
git push
```

진행 중인 병합 자체를 취소하려면 `git merge --abort`를 사용합니다.
