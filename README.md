# ALTA SYSTEM

公開URL: https://alta-system.github.io/

- [使い方](https://alta-system.github.io/help.html)
- [API接続設定](https://alta-system.github.io/guide.html)
- [架空データのデモ](https://alta-system.github.io/?demo=1)

FAA・ICAOのNOTAMに対象を限定しています。NOAA/SIGMET/NOTACは接続しません。
現在は実APIの利用承認・認証情報・スキーマ確認待ちです。実データ画面は未接続と表示し、架空データはweb/demoに分離します。
実運航には使用できません。海域上のNOTAMと海上航行警報（NAVAREA等）は別系統で、後者は未接続です。

## API接続の状態

scripts/update_live.py がFAA/ICAO公式ドメイン、provider、schema_verifiedを検査し、設定済みの全件JSONを国別に処理します。
未設定の国はネットワーク呼出しをせず「unconfigured」を出力します。
FAA専用認証・AIXM・差分処理などのアダプターは、支給される仕様とレスポンスを確認した後に確定します。
ミサイル・ロケット・射撃・軍事演習の語句は危険候補として抽出します。活動の実施を断定する処理ではありません。

FAA NMS: https://www.faa.gov/about/initiatives/notam/faqs
API申請窓口: 7-AWA-NAIMES@faa.gov。無料可否、対象範囲、公開JSON保存と再配布の許諾を申請時に確認してください。
ICAO: https://www.icao.int/api-data-service （公式無料案内は試用25回。永久無料ではありません）

GitHub SecretsにFAA_API_KEY / ICAO_API_KEYを登録する環境変数配線は準備済みです。
キーはチャットや公開ファイルに載せず、GitHubのSettings > Secrets and variables > Actionsへ直接登録してください。
LIVE_DATA変数は不要です。デモと実データを毎回別に生成します。

## 開発・公開

python -m unittest discover -s tests -v
python scripts/update_airspace.py --demo --output web/demo
python scripts/update_live.py
python -m http.server 8000 --directory web

PagesのSourceはGitHub Actions。ユーザー名alta-systemとリポジトリ名alta-system.github.ioの組み合わせでルートURLに公開します。
UTC毎時07分・37分の取得予定。遅延・停止・API利用制限があるため、即時性や無保守での永久稼働は保証しません。

## 既存の共通JSON契約と形状処理

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
- 対象はNOTAMのみです。一般気象データの取得処理はありません。

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

実NOTAM API接続は未検証です。デモのActions・Pages公開と基本操作は確認済みです。

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
