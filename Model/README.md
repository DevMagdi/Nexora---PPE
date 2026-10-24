# Industrial inference weights

Install the approved `ppe.pt` artifact in this directory (`Model/ppe.pt`). It is
the only checkpoint the application accepts: the file name is checked before and
after `resolve()`, and any unified name (`ppe_unified_best.pt` or anything
containing `unified`) aborts startup with
`Only approved weight Model/ppe.pt is allowed; unified weights are rejected.`
Weights are deployment artifacts, not substituted or renamed checkpoints. No
automatic download or fallback exists.

The recommended pin is
`PPE_MODEL_SHA256=15c758c669eeb557d9439bd18c5a3929680238122a95286210ca69e11af8218a`
and is enforced whenever it is configured.

The full contract is in [`docs/PPE_WEIGHT_POLICY.md`](../docs/PPE_WEIGHT_POLICY.md).
Run `python -m app.model_check` before starting the pilot. The command validates
the file, industrial class vocabulary and optional SHA-256 pin. The service
fails closed if the artifact is missing, empty, incompatible or corrupt.

## Actual checkpoint capabilities

The minimum contract is Person, Hardhat, NO-Hardhat and Safety Vest, not every
positive/negative pair. Missing NO-Safety Vest disables the vest **negative
alert rule only**, never positive vest display or startup. Other supported
negative rules are discovered from the actual class map, not invented.

The 13 expected classes are Hardhat, NO-Hardhat, Safety Vest, NO-Safety Vest,
Mask, NO-Mask, Person, Gloves, NO-Gloves, Safety Boots, NO-Safety Boots, Goggles
and NO-Goggles. Boots/NO-Boots/NO-Safety Boots normalize to Safety Boots/NO-Boot.
Mask/NO-Mask and any other non-industrial labels are ignored at display and rule
level, never turned into product classes, and never block startup. Ladder, Cone
and Excavator are not required.
The shared PPE resolver runs before preview, counts and sustained alerts;
see `docs/MANTIK_PPE_UPDATE.md` for the deterministic conflict policy. Passing
class compatibility is not evidence of accuracy on a real industrial site.
