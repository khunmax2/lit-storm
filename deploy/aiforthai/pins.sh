# Source me (`. deploy/aiforthai/pins.sh`): exports the commits stack/engines.lock.json
# pins, which deploy/aiforthai/compose.yml builds the Engine forks and MRA from.
# POSIX sh and sed only: the runner's default image has no Python or jq.
_lock="${PINS_LOCK:-stack/engines.lock.json}"
_pin() {
  sed -n "/\"$1\": {/,/}/s/.*\"commit\": *\"\([0-9a-f]\{40\}\)\".*/\1/p" "$_lock"
}
AGENTS_REF=$(_pin agents)
DEEP_REF=$(_pin deep)
MRA_REF=$(_pin mra)
MRA_SEARXNG_REF=$(_pin mra_searxng)
export AGENTS_REF DEEP_REF MRA_REF MRA_SEARXNG_REF
for _v in AGENTS_REF DEEP_REF MRA_REF MRA_SEARXNG_REF; do
  eval "[ -n \"\$$_v\" ]" || { echo "!! $_v not found in $_lock" >&2; return 1 2>/dev/null || exit 1; }
done
echo "pins: agents=$AGENTS_REF deep=$DEEP_REF mra=$MRA_REF mra_searxng=$MRA_SEARXNG_REF"
unset _lock _v
unset -f _pin
