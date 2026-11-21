# Pixel Eye 기여 안내

Pixel Eye는 PNG/JPEG/WebP를 로컬에서 디코딩하고, 같은 좌표와 RGBA 값을 SVG 사각형으로 내보냅니다. 모델 호출, 이미지 업로드, 자동 보정은 하지 않습니다. 이미지 변환의 기준과 지원 범위는 [출력 계약](docs/limits.md)을 참고하세요.

## 시작하기

저장소 루트에서 Python 3.10 이상을 사용합니다. 가상 환경을 활성화한 뒤 아래 명령을 실행하세요.

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest -v
```

기여 안내 작성 시 확인한 테스트는 17개입니다. 변환기나 검증기를 수정할 때는 기존 테스트에 더해 **바뀐 조건에서 통과해야 할 사례와 실패해야 할 사례**를 추가하세요. 특히 좌표 원점, 투명도, 가로 묶음, 기존 파일 보존을 확인합니다.

## 버그 신고와 변경 제안

- 운영체제, Python/Pillow 버전, 실행 명령, 기대 결과와 실제 결과를 적어 주세요. 픽셀 오류는 첫 불일치 좌표와 마스크 또는 색/알파 중 무엇이 달랐는지 적으면 도움이 됩니다.
- 실제 작업 이미지 대신 직접 만든 작은 테스트 패턴으로 재현해 주세요. 비공개 사진, 고객 파일, 제3자 스프라이트, 원본에서 변환한 SVG/PNG, 메타데이터가 담긴 로그는 이슈·PR에 올리지 마세요. 자료를 공개할 권리가 명확한 경우에만 예제를 첨부합니다.
- 변경 하나당 목적 하나를 설명하고, 테스트 명령과 결과를 PR에 남겨 주세요. 검증 조건을 약화시키는 변경, 출력 계약 변경 또는 외부 접근 추가는 구현하기 전에 먼저 제안해 주세요.
- 저장소에 별도 라이선스 파일이 없습니다. 이 안내는 사용·재배포 권한 또는 별도 기여 약관을 부여하지 않습니다.

## 한 픽셀 오류 재현

아래 명령은 매번 새 임시 폴더에 직접 만든 2×1 테스트 이미지를 씁니다. 먼저 정상 SVG를 검증한 뒤 오른쪽 픽셀만 바꿉니다. macOS/Linux 셸 기준입니다.

```sh
WORK=$(mktemp -d)
python - "$WORK" <<'PY'
from pathlib import Path
import sys
from PIL import Image
root = Path(sys.argv[1])
im = Image.new("RGBA", (2, 1), (48, 112, 208, 255))
im.putpixel((1, 0), (240, 192, 48, 255))
im.save(root / "fixture.png")
PY
python pixel_eye.py --root "$WORK" fixture.png good.svg
python verify_pixels.py --root "$WORK" fixture.png good.svg
python - "$WORK" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
svg = (root / "good.svg").read_text()
assert svg.count("#f0c030") == 1
(root / "bad.svg").write_text(svg.replace("#f0c030", "#f0c031"))
PY
python verify_pixels.py --root "$WORK" fixture.png bad.svg
```

마지막 검증은 `pixel differs at (1, 0)`을 표시하고 종료 코드 2를 반환해야 합니다.

구성 참고: [GitHub Docs](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors)의 루트 기여 안내 파일 방식과 [Pillow 테스트 안내](https://github.com/python-pillow/Pillow/blob/main/Tests/README.rst)의 테스트 실행법 분리 방식을 따랐습니다. 명령, 예제 및 기준은 이 저장소에 맞춰 작성했습니다.
