# 꿈풀이 사전

꿈해몽 키워드로 검색 유입을 검증하기 위한 정적 사이트입니다.
매일 아침 자동으로 ① 실제 검색되는 꿈 키워드를 찾고 ② 페이지를 만들고 ③ 배포합니다. 서버 비용은 0원이고, 드는 비용은 도메인과 Claude API 사용료뿐입니다.

```
config.json                 사이트 이름, 주소, 애드센스·GA·인증 코드, 생성 개수
keywords/seeds.txt          시드 키워드 (분류별). 여기에 추가만 하면 됨
data/keywords.json          키워드 대기열/완료/실패 기록 (자동 관리)
content/dreams/*.json       꿈 페이지 원고 (자동 생성, 직접 고쳐도 됨)
content/drafts/             auto_publish=false일 때 검토 대기 원고
scripts/expand_keywords.py  구글·네이버 자동완성으로 키워드 발굴
scripts/generate.py         Claude API로 원고 생성 + 품질 검사
scripts/build.py            dist/ 정적 사이트 빌드
scripts/daily.py            확장 → 생성 순서로 실행
.github/workflows/daily.yml 매일 오전 6시(KST) 자동 실행·배포
```

## 매일 자동으로 일어나는 일

1. **키워드 발굴**: 시드("뱀")로 구글·네이버 자동완성을 조회해 "뱀에게 물리는 꿈"처럼 실제로 검색되는 꿈을 대기열에 넣습니다. 자동완성 키워드가 대기열 맨 앞으로 갑니다. 시드를 다 쓰면 이미 만든 페이지 키워드로 한 단계 더 파고듭니다.
2. **페이지 생성**: 대기열에서 하루 `pages_per_day`개를 꺼내 원고를 만듭니다. 글자 수, 상황별 풀이 개수, FAQ, 제목의 키워드 포함 여부를 검사해서 기준 미달이면 이유를 알려주고 한 번 다시 쓰게 하고, 그래도 안 되면 버리고 `failed`에 기록합니다.
3. **관련 꿈 연결**: 원고의 '관련 꿈' 중 아직 없는 키워드는 대기열에 들어가 사이트가 스스로 넓어집니다. 이미 있는 페이지끼리는 내부 링크로 이어집니다.
4. **배포**: 새 원고를 저장소에 커밋하고, 사이트를 빌드해 GitHub Pages에 올립니다. sitemap.xml, rss.xml도 매번 갱신됩니다.

## 처음 설정 (30분 정도)

### 1. 도메인 준비
애드센스는 `github.io` 주소로는 승인받을 수 없어서 **직접 소유한 도메인이 필요**합니다. 가비아, Cloudflare, Namecheap 등에서 하나 구입하세요.

### 2. GitHub 저장소 만들기
```bash
cd dream-site
git init && git add . && git commit -m "첫 커밋"
git branch -M main
git remote add origin https://github.com/<아이디>/<저장소>.git
git push -u origin main
```

### 3. GitHub 설정
- **Settings → Pages → Source**를 `GitHub Actions`로 바꿉니다.
- **Settings → Secrets and variables → Actions → New repository secret**에서 `ANTHROPIC_API_KEY`를 추가합니다. (console.anthropic.com에서 발급)
- **Settings → Pages → Custom domain**에 도메인을 입력하고, 도메인 업체 DNS에 GitHub이 안내하는 레코드를 추가합니다. 연결되면 `Enforce HTTPS`를 켭니다.

### 4. config.json 수정
- `site_url`: `https://내도메인.com` (끝에 / 없이)
- `contact_email`: 문의 받을 메일
- 저장 후 push하면 바로 다시 배포됩니다.

### 5. 첫 실행
**Actions 탭 → 매일 꿈해몽 페이지 생성·배포 → Run workflow**로 한 번 돌려 보세요. 초반에는 `pages`에 20 정도를 넣어 기본 페이지를 채워도 됩니다.

### 6. 검색엔진 등록 (가장 중요)
- **Google Search Console**: 도메인 추가 → HTML 태그 인증 코드의 `content` 값을 `google_site_verification`에 넣고 배포 → 인증 → `sitemap.xml` 제출
- **네이버 서치어드바이저**: 사이트 등록 → 인증 코드를 `naver_site_verification`에 넣고 배포 → 인증 → `sitemap.xml`과 `rss.xml` 모두 제출. 꿈해몽은 네이버 검색 비중이 커서 이 단계를 빼면 안 됩니다.
- **GA4** (선택): 측정 ID(`G-XXXX`)를 `ga4_id`에 넣으면 방문 통계와 사이트 내 검색어가 기록됩니다.

### 7. 애드센스 연동
1. adsense.google.com에서 사이트를 추가하고 게시자 ID(`ca-pub-로 시작`)를 받습니다.
2. `adsense_client`에 `ca-pub-XXXXXXXXXXXXXXXX`를 넣고 배포합니다. 그러면 자동으로
   - 모든 페이지에 애드센스 코드와 계정 메타 태그가 들어가고
   - `/ads.txt`가 생성되며
   - 애드센스의 '자동 광고'가 켜져 있으면 바로 광고가 붙습니다.
3. 애드센스 화면에서 사이트 소유권 확인 → 검토 요청.
4. 승인 후 광고 위치를 직접 정하고 싶으면 '디스플레이 광고' 단위를 만들어 슬롯 번호를 `ad_slots`에 넣으세요. 본문 위, 상황별 풀이 3번째 뒤, 본문 끝 세 곳에 들어갑니다. 비워 두면 자동 광고에 맡깁니다.

## 로컬에서 돌려 보기
```bash
python3 scripts/build.py                  # dist/ 생성
cd dist && python3 -m http.server 8000    # http://localhost:8000
export ANTHROPIC_API_KEY=sk-ant-...
python3 scripts/daily.py --pages 3        # 키워드 확장 + 3개 생성
```
외부 패키지 없이 파이썬 3.10 이상만 있으면 됩니다.

## 검증을 어떻게 볼지

| 시점 | 볼 것 | 어디서 |
|---|---|---|
| 1~2주 | 색인된 페이지 수 | Search Console '페이지', 네이버 '수집 현황' |
| 3~4주 | 노출수가 생기는 키워드 | Search Console '실적' |
| 4~8주 | 클릭수, 평균 게재순위 20위 안 키워드 비율 | Search Console, 네이버 '검색 유입' |
| 애드센스 후 | 페이지 RPM | 애드센스 보고서 |

신규 도메인은 첫 한 달 동안 유입이 거의 없는 게 정상입니다. 판단은 최소 6~8주 뒤에 하세요.
GA4를 켰다면 `search` 이벤트에서 **결과가 0개였던 검색어**를 확인해 `seeds.txt`에 추가하면, 방문자가 실제로 원하는 꿈부터 채울 수 있습니다.

## 조정 가능한 값 (config.json → generation)
- `pages_per_day`: 하루 생성 개수 (기본 5)
- `expand_seeds_per_day`: 하루 자동완성 조회할 시드 수 (기본 8)
- `auto_publish`: `false`로 바꾸면 원고가 `content/drafts/`에 쌓이고, 검토한 파일만 `content/dreams/`로 옮겨 발행합니다.
- `model`: 사용할 Claude 모델

## 운영 시 주의할 점
- **하루 생성량은 천천히 늘리세요.** 구글은 검색 순위를 노리고 대량 생성한 저품질 페이지를 '스팸성 대량 콘텐츠'로 보고 사이트 전체의 노출을 떨어뜨립니다. 기본값 5개는 이 위험을 낮추려는 선택입니다. 색인이 잘 되는 걸 확인한 뒤 늘리는 편이 안전합니다.
- **애드센스는 첫 심사에서 '가치가 별로 없는 콘텐츠'로 거절되는 경우가 많습니다.** 페이지가 30~50개 쌓이고, 인기 키워드 몇 개는 직접 읽고 다듬은 뒤 신청하는 것을 권합니다.
- 원고 JSON은 직접 고쳐도 됩니다. 고친 뒤 `updated` 날짜를 바꾸면 사이트맵에도 반영됩니다.
- API 사용료는 페이지당 입력 약 2천 토큰, 출력 약 3~4천 토큰 수준입니다. 모델별 단가는 Anthropic 가격 페이지를 확인하세요.
