# 🚀 Render無料クラウド サーバーデプロイ手順書 (完全無料・カード不要)

このプロジェクトは、**Render (render.com)** の無料枠を使って、自宅PCの電源を切っていても24時間いつでもスマホから最新価格を取得できる完全固定URLサーバーとして動作するように改修済みです。

---

## 🌟 クラウド化によるメリット
1. **URLが一生固定**: 例 `https://apple-kaitori-xxx.onrender.com`
2. **自宅PCを閉じても稼働**: PCの電源を消していても、スマホのブラウザで開くだけで即座に最新価格を取得。
3. **完全無料**: クレジットカード不要で無料枠内で運用可能。
4. **自動定期更新**: クラウド上で1時間おきに最新買取価格を自動更新。手動で「🔄 今すぐ調査」を押してもその場で再スクレイピングします。

---

## 📋 デプロイ手順（3ステップ・所要時間 約3分）

### ステップ 1: GitHubにリポジトリを作成する
1. ブラウザで [GitHub](https://github.com/)（アカウントがなければ無料作成）にログインし、右上の **「+」** → **「New repository」** をクリックします。
2. リポジトリ名を入力します（例: `apple-kaitori-finder`）。
3. **「Public」** または **「Private」** を選び、画面下の緑色のボタン **「Create repository」** を押します。
4. 作成されたリポジトリのURL（例: `https://github.com/ユーザー名/apple-kaitori-finder.git`）をコピーします。

### ステップ 2: プロジェクトをGitHubにアップロードする
1. フォルダー内の `push_to_github.bat` をダブルクリックして実行します。
2. 先ほどコピーしたGitHubリポジトリのURLを貼り付けて Enter を押します。
3. 自動的にファイルがGitHubにアップロードされます。

### ステップ 3: RenderでWebサービスを作成する
1. ブラウザで [Render 公式サイト (render.com)](https://render.com/) にアクセスし、**「Sign Up」** をクリックします。
   * **「GitHubでログイン」** を選ぶと連携が最もスムーズです（カード登録不要）。
2. ダッシュボード画面右上の **「New +」** ボタン → **「Web Service」** をクリックします。
3. **「Connect a repository」** で、ステップ1で作成した `apple-kaitori-finder` を選び **「Connect」** を押します。
4. 設定画面が表示されますが、プロジェクト内の `render.yaml` により自動入力されます：
   * **Name**: 好きな名前（例: `apple-kaitori`）
   * **Region**: `Singapore` (日本に近いため最速)
   * **Branch**: `main`
   * **Runtime**: `Python`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `python mobile_server.py --cloud`
   * **Instance Type**: **`Free`** (0$/月) を選択
5. 画面一番下の **「Create Web Service」** をクリックします。

---

## 🎉 完了！
約1〜2分でビルドが完了し、画面左上にあなた専用の固定URL：
```text
https://apple-kaitori-xxxx.onrender.com
```
が表示されます！

* このURLをスマホ（iPhoneのSafariやAndroidのChrome）で開いて**「ホーム画面に追加」**すれば、PCを一切立ち上げなくても、いつでも最新の買取価格・利益判定が手に入ります。
* 画面右上の **「🔗 共有」** ボタンを押せば、他の人に教えるための公開URLもワンタップでコピーできます。
