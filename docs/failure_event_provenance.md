# MetroPT-3 Failure-Event Provenance

## Governed source identity

| Field | Verified value |
|---|---|
| Dataset | MetroPT-3 Dataset |
| Publisher | UCI Machine Learning Repository |
| DOI | `10.24432/C5VW3R` |
| Collection period | February through August 2020 |
| Local analytical coverage | `2020-02-01 00:00:00` through `2020-09-01 03:59:50` |
| Source section | Additional Information - Failure Information |
| Accessed | July 30, 2026 |

The UCI source explicitly describes MetroPT-3 as unlabeled and provides the
failure reports separately. The records below are governed event metadata, not
a target column and not row-level labels.

## Documented intervals

| Event ID | Start | End | Failure | Severity | Source status |
|---|---|---|---|---|---|
| `uci_air_leak_2020_04_18` | `2020-04-18 00:00` | `2020-04-18 23:59` | Air leak | High stress | Documented; exact dataset match |
| `uci_air_leak_2020_05_29` | `2020-05-29 23:30` | `2020-05-30 06:00` | Air leak | High stress | Documented; exact dataset match; one unresolved note conflict |
| `uci_air_leak_2020_06_05` | `2020-06-05 10:00` | `2020-06-07 14:30` | Air leak | High stress | Documented; exact dataset match |
| `uci_air_leak_2020_07_15` | `2020-07-15 14:30` | `2020-07-15 19:00` | Air leak | High stress | Documented; exact dataset match |

## Preserved conflict

The source entry for the May 29-30 event says `Maintenance on 30Apr at 12:00`.
That note conflicts with the event dates. The project preserves the text as an
unresolved source conflict and does not silently rewrite either the note or the
documented event interval.

## Scope boundary

This provenance record does not define healthy intervals, prediction windows,
row-level labels, features, models, or performance claims. Any later label
materialization must remain inside the 364 verified observation segments and
must not cross the 363 documented temporal gaps.
