# AIRSPACE ATLAS

Python + GitHub Actions + 国別JSON + GitHub Pages + Leaflet 1.9.4 の基本テンプレートです。データベース・常駐バックエンド・npmビルドは不要。日本語のウェブマップと導入ガイドを同梱しています。

**初期状態は架空データです。世界の航空局への実接続は未設定です。実運航用ではありません。**

## できること

- JP / KR / US / GB / AU をループ。対象国は設定で追加・削除できます。
- Restricted / Danger / Prohibited、Qコード、指定キーワードから候補を抽出。
- Polygon / MultiPolygon（穴を保持）、明示的な円、Q行の概略円を描画。
- 国別タブではなく「地域タブ＋国選択」の構成。区域名・識別子・本文・Qコードで検索。
- URLで閲覧対象を指定。ユーザー間で選択状態を共有せず、サーバーに個人設定を保存しません。
- UTC毎時07分・37分に取得→国別JSONをコミット→同じActionsでPagesを公開。
- 取得失敗時は前回の正常なスナップショットを保持。最終成功時刻は更新しません。
- 期限切れと明示的な取消を除外。座標不明は「未描画」に表示。

## まずMacで見る

Python 3.10以上を使用します。外部Pythonパッケージは不要です。

```bash
cd airspace-pages
python3 scripts/update_airspace.py --demo
python3 -m http.server 8000 --directory web
```

ブラウザーで http://localhost:8000 を開きます。HTMLの直接ダブルクリックではJSON取得が動きません。Leafletと地図タイルはインターネット接続が必要です。

```text
http://localhost:8000/?country=JP
http://localhost:8000/?countries=JP,KR,US,GB,AU
http://localhost:8000/?countries=JP,KR&region=Asia&country=KR
```

`countries`は画面に出す国の集合、`country`は初期選択国、`region`は`Asia / Americas / Europe / Oceania / Africa`です。設定外の国は表示しません。URLは閲覧フィルターでありアクセス制限ではありません。公開JSONは誰でも取得できます。

## GitHub Pagesで公開する手順

1. GitHubで公開リポジトリ `airspace-atlas` を作ります。無料での運用を想定するためPublic、デフォルトブランチは`main`。
2. このフォルダーの**中身**をリポジトリのルートにアップロードします。Macで隠しファイルを表示するにはCommand + Shift + .。`.github/workflows/update-and-deploy.yml`も必ず含めます。ZIPをそのまま置くだけでは動きません。
3. `Settings → Pages → Build and deployment → Source`を **GitHub Actions** にします。
4. `Settings → Actions → General`でActionsを有効にし、ワークフローがリポジトリへ書き込めることを確認します。組織ポリシーやmainの保護規則が書込を禁止する場合は、管理者承認や許可された更新方法が必要です。
5. `Actions → Update airspace and deploy Pages → Run workflow`を実行します。成功するとPagesの設定画面・ActionsのDeployment欄に公開URLが表示されます。
6. 初期状態はデモです。実API設定が完了したら、下記の`LIVE_DATA=true`を設定して再実行します。

Gitを使用する場合（URLはご自身のリポジトリに置き換えてください）：

```bash
git init -b main
git add .
git commit -m "Add Airspace Atlas template"
git remote add origin https://github.com/YOUR_ACCOUNT/airspace-atlas.git
git push -u origin main
```

GitHubへの認証はGitHub公式の方法で行ってください。APIキーをコミットしないでください。

GitHub PagesのURLは通常 `https://YOUR_ACCOUNT.github.io/airspace-atlas/` です。このテンプレートは相対パスを使用しているため、サブディレクトリでも動きます。

## 実APIを接続する

**国際共通の無料NOTAMポリゴンAPIはこのテンプレートに含まれていません。API URLを想像で埋めることはしていません。** ICAO等はアクセス申請・キー・利用条件の確認が必要です。OpenSkyの航空機位置情報はNOTAM境界の代替ではありません。

各国のAPI仕様から、認証、対象範囲、ページング、全件/差分、時刻、座標系、取消・置換、再配布条件を確認し、`config/sources.json`の各国の`api`を埋めます。取得可能な国だけ残して構いません。

```json
{
  "q_prefixes": ["WMR", "WMW", "WXX"],
  "countries": {
    "JP": {
      "name": "日本",
      "region": "Asia",
      "source": "契約・利用許諾済みの提供元名",
      "api": {
        "url": "https://YOUR-VERIFIED-PROVIDER/airspaces?country={country}",
        "snapshot_confirmed": true,
        "records_path": "items",
        "next_path": "next",
        "complete_path": "complete",
        "headers_env": {"X-API-Key": "NOTAM_API_KEY"}
      }
    }
  }
}
```

これは**形式の説明用URL**です。実在するAPIのアドレスではありません。各国に別のURL・キー環境変数を設定できます。対象APIがISO国コードを受け付けない場合は、FIR/ICAOコードへの変換を提供元別アダプターに実装してください。APIキーがクエリパラメータで必要な提供元には、その認証方式をアダプターで追加してください。フロントエンドにはキーを渡しません。

GitHubの`Settings → Secrets and variables → Actions`で：
- Secretsに`NOTAM_API_KEY`を登録。
- Variablesに`LIVE_DATA` = `true`を登録。
- 別名のキーを使う場合はワークフローの`env`にもSecretsから渡します。

### 想定APIレスポンスとアダプター

```json
{
  "complete": true,
  "next": null,
  "items": [{
    "id": "PROVIDER-ID",
    "name": "対象区域",
    "type": "Restricted",
    "qcode": "QRRCA",
    "text": "RESTRICTED AREA ...",
    "status": "ACTIVE",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[139,35],[140,35],[140,36],[139,35]]]
    },
    "validFrom": "2026-10-03T00:00:00Z",
    "validTo": "2026-10-04T00:00:00Z",
    "lower": "SFC",
    "upper": "FL150"
  }]
}
```

GeoJSONは**[経度, 緯度]**、WGS84の十進度です。リングは明示的に閉じます。高度は原文を保持し、3D形状には変換しません。

円の場合は`geometry`の代わりに：

```json
"circle": {"center": [139.5,35.5], "radius": 10, "unit": "NM"}
```

NM / KM / Mに対応。1 NM = 1852 m。Leafletの`L.circle`には半径をメートルで渡します。`qline`しかない場合は最後の`DDMMNDDDMMERAD`を解析し、**概略円**と明示します。半径000/999は境界として扱いません。Q行の円は精密境界ではなく影響範囲を包含するための情報です。

提供元のフィールド名が違う場合は`config/provider.example.json`の`field_map`を必要な項目だけ設定します。ドット区切りでネストした値を取得できます。`field_map`で指定したキーが欠けた場合は国単位の更新を失敗扱いとし、前回データを保持します。GeoJSON FeatureCollectionを受けるなら`records_path: "features"`と`type: "properties.type"`等のマッピングが必要です。

`next_path`を指定しない場合はページングなしとみなします。APIがページングする場合は必ず指定・調整してください。`next`がURLでない提供元、OAuth、AIXM、DMS、圏域コード変換、差分配信には`fetch_snapshot`/`adapt`の提供元別実装が必要です。テンプレートは完全な最新スナップショットを前提とし、`snapshot_confirmed=true`はその確認を済ませた場合だけ設定します。差分APIを全件として扱うと区域が消えるため、そのまま接続してはいけません。

## Qコードと精度の扱い

- 基本の正式QコードはQを含めた5文字です。例：`QRRCA`。`WMR/WMW/WXX`を完全な正式コードと決めつけず、ユーザー指定の前方一致フィルターとして設定しています。
- `QRR..` / `QRD..` / `QRP..`をそれぞれRestricted / Danger / Prohibitedの候補として抽出します。
- `WMR/WMW/WXX`だけで全危険NOTAMを網羅できません。追加コードは提供元の仕様とICAOのコード表に合わせます。
- キーワード一致は候補抽出です。「制限解除」等も拾う可能性があります。運航上の有効性を自然言語だけで断定しません。
- 正確に描けるのは提供元が境界・円を明示している場合です。テキスト中の座標を無条件につないで境界を作ることはしません。
- Polygonの閉鎖・範囲・点数は検査しますが、自己交差等の完全な地理トポロジー検証は提供元アダプターで行う必要があります。
- 日付変更線を跨ぐ未分割Polygonは誤描画を避けて「未描画」にします。RFC 7946に従って提供元アダプターでMultiPolygonに分割してください。極域・非常に大きい円はLeafletの投影誤差があるため精密な測地表示ではありません。
- B/C時刻はISO 8601 UTCへ変換して渡します。未来の区域は「開始前」。D欄の断続スケジュールは表示のみで、稼働判定は未実装です。
- 明示的なCANCELLED / INACTIVE / notamType=C、`cancels`/`replaces`参照と期限切れを処理します。取消・置換の全履歴解決は提供元の完全スナップショットで保証してください。
- SIGMET・火山灰警報等も境界と危険分類を正規化して渡せば描けますが、各形式専用パーサーは含みません。

## データ構造

- `web/data/index.json`：国名・地域・ファイル名・件数・取得状態。
- `web/data/JP.json`等：GeoJSON FeatureCollectionと`metadata`、`unplotted`。
- `lastAttempt`と`lastSuccess`を分離。取得成功から60分超で古いデータと表示。
- フロントエンドは30分ごと、および画面へ戻った時に再取得。最大で更新周期＋次の再取得＋Actions/CDNの遅延があります。即時リアルタイムではありません。
- データ0件と取得失敗は別の状態です。ライブ切替時にデモを前回データとして残しません。
- 失敗した国があっても他国を公開。最後にワークフローを失敗状態にしてGitHub側でも気付けるようにします。

## 無料運用の現実的な範囲

公開リポジトリの標準GitHub-hosted runnerとGitHub Pagesを利用する構成です。追加の有料runner・独自ドメイン・DBは不要ですが、API提供元の料金や再配布制限は別です。無料を維持するには無料・再配布可能なソースだけ設定してください。

Actionsには混雑による遅延・欠落、公開リポジトリの60日無活動による定期実行停止があります。無料条件やサービス終了の可能性もあるため永久稼働は保証できません。データ・地図の取得先が変われば設定変更が必要です。

JSONは国別に圧縮的な書式で保存し、原文APIレスポンスやDBを持ちません。**ファイルを上書きしてもGitの履歴は増えます**。時刻の更新も差分です。長期運用ではリポジトリ容量・実行ログ・Actions通知を時々確認してください。履歴の強制書き換えは自動化していません。

OSM標準タイルはベストエフォートで容量制限があります。大量利用・一括取得・オフライン保存は不可。利用が増えたら適切なタイル提供元へ切り替えます。サイトは通常のブラウザーキャッシュ・出典表示を使い、タイルの定期一括取得は行いません。

## ファイルと検証

| ファイル | 役割 |
|---|---|
| `scripts/update_airspace.py` | 取得・フィルター・座標検査・国別出力 |
| `config/sources.json` | 対象国・API設定 |
| `config/provider.example.json` | アダプター設定例 |
| `fixtures/*.json` | 架空の入力データ |
| `web/index.html`, `web/app.js`, `web/style.css` | Leafletウェブマップ |
| `web/guide.html` | ブラウザーで読める導入ガイド |
| `.github/workflows/update-and-deploy.yml` | 30分取得＋コミット＋Pages公開 |
| `tests/test_update.py` | 抽出・単位換算・取消・保持の回帰テスト |

```bash
python3 -m unittest discover -s tests -v
```

作成時点でPythonの回帰テスト13件とJavaScript構文検査は通過しました。実API、GitHub上でのActions実行・Pages公開、ブラウザーでの視覚・操作確認は未実施です。

認証不要の静的サイトなので複数ユーザーが同時に閲覧できます。個人アカウント・権限管理・編集保存は含めていません。フロントはビルド不要のJavaScriptにし、React/JSXの依存は外しています。Leafletは標準で平面地図であり、3D地球儀はこの構成に含みません。

## 参照した一次資料

- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://leafletjs.com/reference.html
- https://operations.osmfoundation.org/policies/tiles/
- https://www.icao.int/api-data-service
- https://swim-eurocontrol.atlassian.net/wiki/spaces/DNOTAM/pages/220791216
- https://datatracker.ietf.org/doc/html/rfc7946#section-3.1.9

このコードはMIT Licenseです。航空データ・地図・Leaflet等の第三者素材には各提供元のライセンスが別途適用されます。
