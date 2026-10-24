# Industrial inference weights

Install the approved `ppe_unified_best.pt` artifact in this directory. It is the
only checkpoint the application accepts. Weights are deployment artifacts, not
substituted or renamed checkpoints. No automatic download or fallback exists.

Run `python -m app.model_check` before starting the pilot. The command validates
the file, industrial class vocabulary and optional SHA-256 pin. The service
fails closed if the artifact is missing, empty, incompatible or corrupt.

## Actual checkpoint capabilities

The minimum contract is Person, Hardhat, NO-Hardhat and Safety Vest, not every
positive/negative pair. Missing NO-Safety Vest disables the vest **negative
alert rule only**, never positive vest display or startup. Other supported
negative rules are discovered from the actual class map, not invented.

Boots/NO-Boots normalize to Safety Boots/NO-Boot. Extra labels such as Mask,
Ladder, Safety Cone and Excavator are ignored, not emitted as product classes.
The shared PPE resolver runs before preview, counts and sustained alerts;
see `docs/MANTIK_PPE_UPDATE.md` for the deterministic conflict policy. Passing
class compatibility is not evidence of accuracy on a real industrial site.
