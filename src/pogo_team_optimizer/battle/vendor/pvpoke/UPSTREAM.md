# Vendored PvPoke battle engine

These files are copied without behavioral changes from the official PvPoke
repository at commit:

`ea601f0a61c548f9140e4605b94a31fa97fe6aba`

Source: <https://github.com/pvpoke/pvpoke>

Included runtime files:

- `src/js/GameMaster.js`
- `src/js/pokemon/Pokemon.js`
- `src/js/battle/Battle.js`
- `src/js/battle/DamageCalculator.js`
- `src/js/battle/actions/ActionLogic.js`
- `src/js/battle/timeline/TimelineAction.js`
- `src/js/battle/timeline/TimelineEvent.js`
- `src/js/training/DecisionOption.js`

The upstream MIT license is preserved in `LICENSE`. `runner.js` is local glue
that supplies the browser globals required by the upstream files and exposes a
batched JSON interface for the Python application.
