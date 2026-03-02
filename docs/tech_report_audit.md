# Audit Report: Technical Report Sanitization (`docs/tech_report.md`)

This report identifies all internal artifacts, Personally Identifiable Information (PII), and broken formatting within the draft `docs/tech_report.md` that must be addressed prior to external open-source release.

## 1. Explicit Warning Headers
The document currently contains internal tracking headers that must be removed.
- **Line 1:** `#TODO: Sanitise for external consumption`
- **Line 2:** `#TODO: Move assets to GH`

## 2. Internal Author Email Addresses
Author attribution currently exposes internal `@google.com` email addresses. These should be removed entirely, or replaced with public GitHub profiles or external-facing contact aliases.
- **Line 10:** `[Ben Trengrove](mailto:bentrengrove@google.com)[Lynn Ou](mailto:lynnou@google.com)[Siva Velusamy](mailto:vsiva@google.com)`

## 3. Internal Google Doc Links
The document references internal, restricted-access Google Docs. This link must be removed, replaced with static text, or updated to point to a public blog post URL once available.
- **Line 19:** `...a [blog post](https://docs.google.com/document/d/1R7v9c1qy-M7-IhN8_EcGRrDe7q7lt_3i9NJv60xqm2o/edit?resourcekey=0-OaRPSkxivRs0lr_be75MQw&tab=t.gx3kyvp5232i) and a GitHub...`

## 4. Broken / Un-rendered Image Links
Several markdown image tags are either broken or relying on internal base64 definitions at the bottom of the file that do not render cleanly on GitHub. These should be migrated to actual `.png`/`.svg` assets hosted in a `docs/assets/` directory.
- **Line 13:** `| ![][image1]  Caution |` (Missing alt text, relies on internal definition)
- **Line 26:** `| ![][image3]  Warning |` (Missing alt text, relies on internal definition)
- **Line 284:** `![][image10]` (Missing alt text, relies on internal definition)

*(Note: There are other image references like `![pass@1][image2]` that are also relying on the base64 footers. The entire base64 image strategy should be refactored for the final release.)*
