# Together_with_my_dog Git 협업 가이드

작성일: 2026-09-20  
대상: Windows PowerShell 또는 VS Code 터미널에서 2명이 같은 GitHub 저장소에 작업하는 경우  
저장소: [mj3876/Together_with_my_dog](https://github.com/mj3876/Together_with_my_dog)

최초 한 번 `clone` → 자기 브랜치 생성 → 매 작업 시작 시 동기화 → 수정·검증 → `add`·`commit`·`push` → PR 리뷰·병합 순서로 진행합니다. 커밋은 내 PC에 기록하고, 푸시는 GitHub의 내 브랜치에 올리며, PR 병합은 그 변경을 `main`에 반영합니다.

## 1. 두 사람의 브랜치 운영 규칙

“작업 브랜치 2개”를 뜻하며, 통합용 `main`을 포함하면 총 3개입니다.

- `main`: 두 사람의 검토가 끝난 결과를 합치는 브랜치. 직접 작업하거나 푸시하지 않습니다.
- `work/person-a`: A 전용 작업 브랜치.
- `work/person-b`: B 전용 작업 브랜치.

브랜치 이름은 예시입니다. 이름을 바꾸면 이후 명령어에서도 일관되게 바꿉니다. 작성일에 원격 저장소를 확인했을 때 기본 브랜치는 `main`이며 작업 브랜치는 아직 없었습니다. 이 문서 작성 과정에서 브랜치를 만들거나 커밋·푸시하지 않았습니다.

A와 B는 각자의 PC에 따로 클론합니다. 같은 폴더를 두 사람이 동시에 수정하지 않습니다. 각자 하나의 작업 브랜치를 계속 사용하므로, 해당 브랜치에서 진행 중인 PR은 한 번에 하나로 유지합니다. PR을 열고 같은 브랜치에 추가로 푸시하면 그 PR에도 변경이 추가됩니다. 다음 작업은 현재 PR 병합 후 시작합니다.

## 2. 최초 1회: 준비와 클론

Git이 설치되어 있는지 확인합니다.

```powershell
git --version
```

명령을 찾지 못하면 [Git 공식 설치 안내](https://git-scm.com/install/windows)를 통해 설치하고 터미널을 다시 엽니다. 두 사람 모두 각자의 GitHub 계정을 사용하고, 저장소 소유자는 동료에게 쓰기 권한을 부여해야 합니다.

**아직 로컬 폴더가 없는 PC에서만** 아래를 실행합니다. 저장 위치는 각자의 PC에 맞게 바꿉니다. 현재 사용자 PC에는 이미 `C:\Users\ms840\mjuser\Together_with_my_dog`가 있으므로 다시 클론하지 않고 3절로 이동합니다.

```powershell
# 저장할 상위 폴더로 이동합니다. 이 경로는 예시입니다.
Set-Location "C:\Users\ms840\mjuser"

git clone https://github.com/mj3876/Together_with_my_dog.git
Set-Location ".\Together_with_my_dog"

git remote -v
git branch --show-current
```

`clone`은 프로젝트 폴더와 Git 이력을 내려받고 `origin` 원격을 설정합니다. 이후 매번 클론하거나 `git init`을 실행할 필요가 없습니다. [Git clone 문서](https://git-scm.com/docs/git-clone)

저장소 폴더 안에서 커밋 작성자 정보를 한 번 설정합니다. 아래 이름과 이메일을 본인의 값으로 바꿉니다. 이 설정은 GitHub 로그인과 별개이며, 이메일은 GitHub에 등록된 이메일 또는 GitHub 설정에서 제공하는 noreply 주소를 사용합니다.

```powershell
git config user.name "본인 이름"
git config user.email "본인의 GitHub 이메일"
git config --get user.name
git config --get user.email
```

HTTPS 인증이 필요하면 Git Credential Manager의 로그인 안내를 따릅니다. 사용자명·비밀번호 방식 입력창에서 인증할 경우 GitHub 계정 비밀번호 대신 적절한 권한의 개인 액세스 토큰을 사용합니다. 토큰을 저장소 URL, 소스 파일, 문서에 넣지 않습니다. [GitHub 인증 안내](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github)

## 3. 최초 1회: 자기 작업 브랜치 생성

먼저 `git status`를 확인합니다. 아래 일반 절차는 미커밋 변경이 없는 상태를 전제로 합니다. 변경이 있으면 이 절 끝의 안내를 먼저 읽습니다.

**A는 자기 PC에서 A용 명령만 실행합니다.**

```powershell
git status
git switch main
git pull --ff-only origin main
git switch -c work/person-a
git push -u origin work/person-a
```

**B는 자기 PC에서 B용 명령만 실행합니다.**

```powershell
git status
git switch main
git pull --ff-only origin main
git switch -c work/person-b
git push -u origin work/person-b
```

`-c`는 새 로컬 브랜치를 만들고, 첫 푸시의 `-u`는 로컬 브랜치가 추적할 원격 브랜치를 연결합니다. 이후에는 `git push`만 사용해도 됩니다.

브랜치가 이미 로컬에 있으면 `git switch work/person-a`로 이동합니다. 원격에만 있으면 다음을 실행합니다. B는 `person-a`를 `person-b`로 바꿉니다.

```powershell
git fetch origin
git switch --track origin/work/person-a
```

**현재 PC처럼 main에 미커밋 변경이 있는 경우:** 먼저 `git status`와 `git diff --stat`로 내용을 확인합니다. 현재 변경을 모두 A가 이어서 맡기로 했다면, 아직 없는 브랜치를 현재 위치에서 `git switch -c work/person-a`로 만들면 변경을 유지한 채 작업을 이어갈 수 있습니다. 그 뒤 5절처럼 필요한 파일만 골라 커밋하고, `git fetch origin`과 `git merge --no-edit origin/main`으로 동기화한 다음 `git push -u origin work/person-a`를 실행합니다. 소유자가 섞인 변경은 먼저 둘이 나눌 범위를 정합니다. 변경을 정리하기 전에는 일반 절차의 `pull`을 실행하지 않습니다.

## 4. 매 작업 시작: 자기 브랜치와 main의 최신 내용 반영

아래는 A 기준입니다. B는 모든 `work/person-a`를 `work/person-b`로 바꿉니다. 명령을 한 줄씩 실행하고 오류가 나면 다음 단계로 넘어가지 않습니다.

```powershell
# 각자 실제 저장소 경로로 이동
Set-Location "C:\Users\ms840\mjuser\Together_with_my_dog"

git status
git switch work/person-a
git fetch origin
git merge --ff-only origin/work/person-a
git merge --no-edit origin/main
git status
```

첫 `git status`에서 미커밋 변경이 있으면 먼저 원래 작업 브랜치에서 커밋하거나 9절처럼 임시 보관합니다. `git fetch`는 원격 이력을 갱신하고, 첫 `merge`는 내 원격 작업 브랜치를, 두 번째 `merge`는 통합 브랜치의 최신 변경을 현재 작업 브랜치에 반영합니다.

`--ff-only`에서 이력이 갈라졌다는 오류가 나면 9절의 푸시 거절 해결 절차를 따릅니다. `origin/main` 병합 중 충돌이 나면 8절에서 해결한 뒤 작업을 시작합니다. [Git pull 문서](https://git-scm.com/docs/git-pull), [Git merge 문서](https://git-scm.com/docs/git-merge)

## 5. 매 작업 완료: 확인 → add → commit → push

파일을 저장하고 변경한 기능에 맞는 실행·테스트를 먼저 합니다. 이 저장소의 실제 실행 절차는 프로젝트 README를 확인합니다.

```powershell
git branch --show-current
git status
git diff
```

현재 브랜치가 자기 작업 브랜치인지 확인합니다. 이어서 **이번 커밋에 포함할 파일만** 추가합니다. 다음은 이 가이드를 수정한 경우의 예시이며, 코드 작업 시에는 실제 수정한 파일 경로로 바꿉니다.

```powershell
git add -- docs/git_collaboration_guide.md
git diff --cached --stat
git diff --cached
git commit -m "docs: Git 협업 가이드 정리"
git push
git status
```

새 파일은 `git diff`에 보이지 않으므로 `git status`와 파일 내용을 함께 확인하고, 추가 후 `git diff --cached`에서 최종 검토합니다. 삭제나 이동도 의도한 변경인지 확인합니다. 삭제 파일을 커밋에 포함할 때도 해당 경로를 명시해 `git add`합니다.

- 커밋 메시지 예시: `feat: 반려견 동반 장소 검색 추가`, `fix: 검색 조건 오류 수정`, `docs: 설치 방법 보완`.
- 첫 푸시에서 upstream이 없다는 오류가 나면 A는 `git push -u origin work/person-a`를 한 번 실행합니다.
- `git add .`는 관련 없는 변경·삭제까지 포함할 수 있으므로, 전체 변경을 확인한 경우에만 사용합니다.
- `.env`, `.secrets/`, API 키, 개인 인증정보, 원본 데이터, 로컬 DB가 포함되지 않았는지 확인합니다.
- `.gitignore`는 이미 추적되는 파일을 자동으로 제외하지 않습니다. 키를 올렸다면 파일 삭제만으로 끝내지 말고 즉시 해당 키를 폐기·재발급하고 이력 정리는 팀과 협의합니다.

이 저장소는 루트 경로를 기본 제외하는 `.gitignore` 허용 목록 방식입니다. 새 폴더가 `git status`에 나오지 않으면 무시 규칙을 먼저 확인하고 필요한 경로만 허용합니다. 이 가이드 파일에는 전용 예외를 추가했습니다. 그 예외를 처음 공유하는 커밋에는 검토한 `.gitignore` 변경도 포함해야 합니다.

```powershell
git check-ignore -v docs/git_collaboration_guide.md
git diff -- .gitignore
# .gitignore의 공유할 변경 구간만 골라 추가
git add -p -- .gitignore
```

마지막 블록은 필요할 때 5절의 커밋 명령 **전에** 실행합니다.

## 6. PR 생성과 리뷰

푸시만으로 `main`에 합쳐지지 않습니다. [저장소 Pull requests](https://github.com/mj3876/Together_with_my_dog/pulls)에서 다음과 같이 진행합니다.

1. `New pull request` 또는 `Compare & pull request`를 선택합니다.
2. **base는 `main`**, compare/head는 **본인의 `work/person-a` 또는 `work/person-b`**로 선택합니다.
3. `Files changed`에서 변경 파일·삭제·비밀정보를 확인합니다. 상대 브랜치를 compare 또는 base로 잘못 선택하지 않습니다.
4. 제목은 변경 결과가 드러나게 작성하고, 본문에 목적·변경 내용·검증 결과를 적습니다.
5. 상대방을 reviewer로 지정합니다. 리뷰 반영은 같은 브랜치에서 수정 → 커밋 → 푸시하면 기존 PR에 추가됩니다.
6. 충돌이 없고, 필요한 검증과 리뷰가 완료되면 지정한 사람이 병합합니다.

PR 본문 예시:

```markdown
## 목적
반려견 동반 장소 검색에서 지역 조건이 적용되지 않는 문제를 수정합니다.

## 변경 내용
- 지역 필터 처리 수정
- 빈 검색 결과 안내 보완

## 검증
- 실행한 명령 또는 직접 확인한 화면:
- 결과:
- 확인하지 못한 항목:

## 함께 확인할 점
- 공통 파일 또는 API 응답 형식 변경 여부:
- 상대 작업과 겹치는 파일:
```

### 두 브랜치로 협업할 때 특히 주의할 점

- **한쪽 PR이 먼저 병합되면 다른 쪽은 최신 main을 다시 반영합니다.** 충돌이 없더라도 기능이 함께 정상 동작하는지 검증합니다. 예: A가 공통 함수 이름을 바꿨다면 B는 그 함수를 호출하는 부분을 확인합니다.
- **브랜치가 다르다고 파일 충돌이 없어지지는 않습니다.** 같은 파일·함수의 동시 수정은 미리 알리고, 파일 이동·대규모 포맷 변경·의존성 변경은 순서를 맞춥니다.
- **동료의 작업 브랜치를 통째로 내 브랜치에 병합하지 않습니다.** 상대의 미완료 작업이 내 PR에 섞일 수 있습니다. 필요한 공통 변경은 먼저 작은 PR로 main에 반영합니다.
- **열린 PR에 무관한 다음 작업을 추가하지 않습니다.** 고정 작업 브랜치에서는 추가 푸시가 기존 PR에 포함됩니다.
- **푸시 후 리뷰 대상이 바뀌면 다시 확인합니다.** 기존 승인만 보고 추가 변경을 건너뛰지 않습니다.
- **두 PR은 순서대로 병합합니다.** 먼저 병합된 결과를 반영한 후 두 번째 PR을 검증·병합합니다.
- **강제 푸시는 일상 절차로 사용하지 않습니다.** `git push --force`로 원격 이력을 덮어쓰거나 `main`에서 이력을 재작성하지 않습니다.

## 7. PR 병합 방식과 병합 후 동기화

이 가이드처럼 **같은 두 작업 브랜치를 계속 재사용할 때는 `Create a merge commit` 방식**을 권장합니다. 작업 브랜치의 커밋 이력을 보존하여 다음 PR의 비교를 이해하기 쉽습니다. 장기 사용 브랜치에 squash를 반복하면 이미 병합한 커밋이 다음 PR에 다시 나타나거나 충돌이 반복될 수 있습니다. [GitHub PR 병합 방식](https://docs.github.com/en/pull-requests/reference/pull-request-merges)

관리자는 해당 병합 방식이 저장소 설정에서 허용되는지 확인합니다. 이 문서에서는 실제 보호 규칙이나 병합 설정을 변경하지 않았습니다. 선형 이력 강제 등으로 merge commit을 사용할 수 없다면, 작업마다 최신 main에서 새 기능 브랜치를 만들고 squash 후 폐기하는 방식으로 팀 규칙을 바꿔야 합니다.

고정 작업 브랜치는 PR 병합 후 삭제하지 않습니다. 저장소의 자동 브랜치 삭제 설정도 관리자와 확인합니다.

A의 PR이 병합된 후 A가 다음 작업을 준비하는 명령입니다. B도 자기 브랜치 이름으로 같은 절차를 수행합니다. 미커밋 변경이 없는 상태에서 실행합니다.

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git switch work/person-a
git merge --ff-only origin/work/person-a
git merge --no-edit origin/main
git push
```

병합 전에 B의 진행 중인 PR을 최신 main에 맞춰야 하는 경우에는 B가 자기 브랜치에서 다음을 실행하고 다시 검증합니다.

```powershell
git switch work/person-b
git fetch origin
git merge --ff-only origin/work/person-b
git merge --no-edit origin/main
# 충돌을 해결하고 변경 기능과 함께 동작하는지 검증한 후 실행
git push
```

관리자에게 권장할 팀 설정은 main 직접 푸시 제한, PR 필수, 상대방 승인 1명 이상, 대화 해결 및 구성된 CI 통과 요구입니다. 실제 사용 가능한 보호 기능은 저장소 플랜·설정에 따라 확인합니다.

## 8. 충돌이 발생했을 때

`git merge --no-edit origin/main`에서 충돌이 발생하면 후속 커밋·푸시를 멈추고 다음 순서로 처리합니다.

```powershell
git status
git diff --name-only --diff-filter=U
```

출력된 파일을 편집기로 열어 충돌 표시를 해결합니다.

```text
<<<<<<< HEAD
현재 내 작업 브랜치 내용
=======
병합하려는 origin/main 내용
>>>>>>> origin/main
```

이 예에서는 `HEAD`가 내 작업 브랜치이고 `origin/main`이 들어오는 쪽입니다. 양쪽의 의도를 반영한 최종 코드로 수정하고 세 가지 표시 줄을 모두 제거합니다. “내 것 전부 유지” 또는 “들어오는 것 전부 유지”를 무조건 선택하지 않습니다. 삭제/수정 충돌이나 바이너리 충돌은 이런 표시가 없을 수도 있으므로 `git status`에 나온 모든 충돌 파일을 확인합니다.

```powershell
# 아래 경로를 실제 해결한 파일로 바꾸어 실행
git add -- "실제/충돌해결한파일"
git diff --name-only --diff-filter=U
git diff --cached
# 미해결 파일 출력이 없고 실행·검증을 완료한 뒤
git commit -m "merge: main 반영 및 충돌 해결"
git push
```

해결을 취소하고 병합 전 상태로 돌아가려면 병합이 진행 중일 때 다음을 사용합니다. 안전하게 취소할 수 있도록 항상 커밋 또는 임시 보관을 끝낸 깨끗한 상태에서 병합을 시작합니다. [Git merge 충돌 처리](https://git-scm.com/docs/git-merge)

```powershell
git merge --abort
```

## 9. 자주 막히는 상황

### push가 rejected / non-fast-forward로 거절됨

원격의 내 브랜치에 내가 아직 받지 않은 커밋이 있을 수 있습니다. 자기 브랜치이고 미커밋 변경이 없는지 확인한 다음 A 기준으로 실행합니다. B는 이름을 바꿉니다.

```powershell
git fetch origin
git log --oneline --left-right HEAD...origin/work/person-a
git merge --no-edit origin/work/person-a
# 충돌이 있으면 8절대로 해결하고 검증한 후
git push
```

예상하지 않은 다른 사람의 커밋이나 강제 푸시 흔적이 있으면 작성자와 확인합니다. 권한 부족이나 보호 규칙 오류는 이 병합 명령으로 해결되지 않으므로 계정·저장소 권한을 확인합니다.

### 미완료 변경 때문에 브랜치 전환·동기화를 못 함

현재 브랜치에서 진행 중인 작업을 임시 보관할 수 있습니다.

```powershell
git stash push -u -m "동기화 전 임시 보관"
```

동기화 후 **원래 작업을 이어갈 브랜치로 돌아왔는지 확인하고** 복원합니다.

```powershell
git branch --show-current
git stash list
git stash apply 'stash@{0}'
git status
```

`stash@{0}`가 방금 보관한 항목인지 먼저 확인합니다. `apply`는 보관본을 남깁니다. 복원 내용과 충돌 해결을 확인하고 안전하게 커밋한 뒤 해당 항목을 `git stash drop 'stash@{0}'`로 정리합니다. 다른 stash가 생겼으면 번호를 다시 확인합니다. `-u`는 추적하지 않는 파일을 포함하지만, 무시된 파일은 포함하지 않습니다.

### add한 파일을 커밋에서 빼고 싶음

`git restore --staged "파일경로"`로 스테이징만 취소합니다. 작업 파일의 수정 내용은 유지됩니다.

### clone 시 destination path already exists

이미 클론한 폴더인지 확인하고 그 폴더로 이동해 `git status`를 실행합니다. 새 복사본이 꼭 필요하다면 다른 폴더 이름을 사용합니다. 기존 작업 폴더를 삭제해서 해결하지 않습니다.

### main에서 작업해 버림

아직 푸시하지 않은 변경이면 3절의 “main에 미커밋 변경이 있는 경우”를 따릅니다. 이미 main에 커밋했거나 원격에 푸시했다면 현재 커밋과 공유 여부를 확인해 별도로 복구 절차를 정합니다. `git reset --hard`나 강제 푸시를 먼저 실행하지 않습니다.

## 10. 익숙해진 뒤 보는 매일 명령 요약

최초 브랜치 생성·upstream 연결을 마친 A 기준입니다. B는 브랜치 이름을 바꿉니다. 오류나 충돌이 나면 멈추고 해당 절을 확인합니다.

**작업 시작 — 미커밋 변경을 먼저 정리합니다.**

```powershell
git status
git switch work/person-a
git fetch origin
git merge --ff-only origin/work/person-a
git merge --no-edit origin/main
```

**작업 완료 — 파일 저장 및 필요한 검증 후 실행합니다.**

```powershell
git branch --show-current
git status
git diff
git add -- "이번에수정한파일경로"
git diff --cached
git commit -m "feat: 이번 작업 내용"
git push
```

**마지막 확인:** PR의 base는 main, compare는 내 브랜치 → 상대 리뷰 → 최신 main 반영·검증 → Create a merge commit → 7절 동기화.

