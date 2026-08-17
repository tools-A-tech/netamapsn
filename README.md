# サブスク棚（Subshelf）

Netflix / Amazonプライム / PS Plus の配信タイトルを、日本のレンタルショップ風の棚UIで探しやすくする静的サイトです。

## 特徴

- **タイトル優先の検索**（関係ない作品が極力出ない）
- ジャンルはデータソースに合わせて**動的に生成**
- 新着・配信終了間近の絞り込み
- 登録順・上映年などでの並べ替え
- 毎日自動更新（GitHub Actions）

## 動作の流れ

1. 毎日 21:50 JST 頃に GitHub Actions が起動
2. `scripts/update_data.py` が JustWatch などからデータを取得
3. `data/titles.json` を更新してコミット
4. GitHub Pages が自動で最新版を配信

## セットアップ手順

### 1. リポジトリ作成

GitHubで新しいリポジトリを作成し、このフォルダの内容をすべてアップロードしてください。

### 2. GitHub Pages を有効化

1. リポジトリの **Settings** → **Pages**
2. Source を **Deploy from a branch** に設定
3. Branch を `main`（または `master`）、folder を `/ (root)` に指定
4. Save

数分後に `https://<ユーザー名>.github.io/<リポジトリ名>/` で公開されます。

### 3. Actions の権限確認

Settings → Actions → General で  
「Workflow permissions」が **Read and write permissions** になっていることを確認してください。  
（JSONをコミットするために必要です）

### 4. 手動で一度動かしてみる

Actions タブ → 「Daily Data Update」→ 「Run workflow」で手動実行できます。

## ファイル構成

```
.
├── index.html              # フロントエンド
├── data/
│   └── titles.json         # 毎日更新されるデータ
├── scripts/
│   └── update_data.py      # データ取得スクリプト
├── .github/workflows/
│   └── update.yml          # 毎日自動更新の設定
└── README.md
```

## 今後の拡張予定

- JustWatch のクエリをより安定したものに調整
- 必要に応じて Playwright によるフォールバック追加
- PS Plus カタログの本格取得
- ポスター画像の安定表示

## 注意

- JustWatch の GraphQL は非公式のため、仕様変更で一時的に取れなくなる可能性があります。
- その場合はスクリプトを修正するか、Playwright 版に切り替えます。
- 個人利用・趣味の範囲での利用を想定しています。
