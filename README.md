# NEON WALK · 네온 거리 산책

캐릭터를 골라 3D 네온 거리와 클럽을 걷는 사이트예요. 같은 주소로 들어온 사람들의 캐릭터와 닉네임이 실시간으로 함께 보여요.

## 폴더 구성

- `server.py`: 사이트 파일을 내보내고, 접속한 사람들의 위치를 서로 전달하는 서버예요. 파이썬 기본 기능만 써서 따로 설치할 게 없어요.
- `public/`: 페이지(`index.html`), 배경(`bg.jpg`), 음악(`bgm.mp3`: 거리, `track.mp3`: 클럽)이 들어 있어요.
- `render.yaml`: Render에 올릴 때 쓰는 설정이에요.

## 내 컴퓨터에서 실행

```
cd ~/neon-walk
python3 server.py
```

브라우저에서 http://localhost:8000 을 열어요. 탭을 두 개 열면 서로의 캐릭터가 보여요.

## Render에 올리기 (무료)

1. GitHub에 로그인하고 새 저장소(예: `neon-walk`)를 만들어요.
2. 저장소 화면에서 **uploading an existing file**을 누르고, 이 폴더 안의 파일과 `public` 폴더를 통째로 끌어다 놓은 뒤 **Commit changes**를 눌러요.
3. https://render.com 에 GitHub 계정으로 로그인해요.
4. **New → Blueprint**를 누르고 방금 만든 저장소를 고른 뒤 **Apply**를 눌러요. `render.yaml`대로 무료 웹 서비스가 만들어져요.
5. 몇 분 뒤 생기는 `https://neon-walk-xxxx.onrender.com` 주소를 공유하면 돼요.

무료 플랜은 15분 동안 아무도 접속하지 않으면 잠들어요. 다음 사람이 처음 들어올 때 30초~1분쯤 걸려요.

## 음악

`public/bgm.mp3`, `public/track.mp3` 파일을 바꾸면 곡이 바뀌어요. 공개 사이트에서는 누구나 이 파일을 듣고 내려받을 수 있으니, 공개 사용 권한이 있는 곡만 넣어 주세요.
