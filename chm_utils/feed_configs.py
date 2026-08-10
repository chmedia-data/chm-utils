"""Resolve a feed config into the concrete config for one portal:variant.

Pure functions, standard library only — no IO, no clients. Shared so that the
consumers which validate these configs and the ones which apply them resolve
them identically.

A config declares its variations at the root and its parameters below.
`get_portal_variant_configs` applies two layers:

1. **Variables** — `$portals` / `$variants` dicts collapse to the value matching
   the portal or variant, with fnmatch patterns and a `default` key.
2. **Overrides** — dot-path assignments declared by a variation, applied on top.

    from chm_utils.feed_configs import get_portal_variant_configs

    configs = get_portal_variant_configs(feed_config, portals=['p1'])
    # {'p1:variant_a': {...}, 'p1:default': {...}}

Overrides are read from two places. A variation randomising across several
variants declares them per entry of `variants`; a variation assigning a single
variant declares them on itself, keyed by its `variant_id`. Variation-level
overrides run first, so the variant level wins where both target a path.
"""

import fnmatch
import json
import re

VARIABLE_KEYS = ["$variants", "$portals"]

ALL_COHORT = "all"


def find_resolve_key(obj, variable_key, portal, variant_id):
    """Return the key of a `$variants`/`$portals` dict to resolve against.

    Resolution order: exact match, then the *longest* matching fnmatch pattern
    (longest wins because it is the most specific — `a_p1_*` beats `a_*`), then
    `default`.

    Raises:
        Exception: no exact match, no matching pattern and no `default` key.
    """
    resolve_key = portal if '$portals' in variable_key else variant_id

    if resolve_key in obj[variable_key]:
        return resolve_key

    matching_keys = [i for i in obj[variable_key].keys() if fnmatch.fnmatch(resolve_key, i)]
    if len(matching_keys) > 0:
        return sorted(matching_keys, key=len, reverse=True)[0]
    elif 'default' in obj[variable_key]:
        return 'default'
    else:
        raise Exception(f"Config variable could not be resolved! Resolve key '{resolve_key}' could not be found in '{','.join(obj[variable_key].keys())}'.")


def replace_variable(obj, variable_key, portal, variant_id):
    """Replace a variable section with its resolved value.

    When the resolved value is a dict it is merged with its parent's remaining
    keys, so siblings of the `$variants` key survive resolution.
    """
    resolve_key = find_resolve_key(obj, variable_key, portal, variant_id)

    new_obj = obj[variable_key][resolve_key]

    if isinstance(new_obj, dict):
        for k, v in obj.items():
            if k != variable_key:
                new_obj[k] = v

    return new_obj


def resolve_variables(obj, portal, variant_id="default", root=None):
    """Recursively collapse every `$variants`/`$portals` section in a config.

    Returns a new object; the input is not mutated.

        {"section": {"$variants": {"a_*": 1, "default": 2}}}
        -> {"section": 1}    # variant_id='a_p1'
    """
    obj = json.loads(json.dumps(obj))

    root = root or obj

    if isinstance(obj, dict):
        matching_variable_key = [i for i in VARIABLE_KEYS if i in obj]

        if len(matching_variable_key) > 0:
            variable_key = matching_variable_key[0]
            return replace_variable(obj, variable_key, portal, variant_id)
        else:
            for k, v in obj.items():
                obj[k] = resolve_variables(v, portal, variant_id, root)
            return obj
    elif isinstance(obj, list):
        return [resolve_variables(i, portal, variant_id, root) for i in obj]
    else:
        return obj


def normalise_cohort(variation):
    """Return the cohort a variation competes in.

    A missing or empty `cohort` means the whole audience, so it normalises to
    `all` — the same pool an explicit `cohort: all` lands in. The api resolving
    these configs treats an empty cohort as matching everyone, so the two have
    to share one allocation pool here too.
    """
    return (variation.get('cohort') or '').strip() or ALL_COHORT


def get_portal_variant_ids(config, portals):
    """List the `portal:variant_id` combinations a config resolves to.

    Variations are grouped by their `cohort`; within a cohort, experiment
    variations consume their `percent` and any other type exhausts the cohort
    (it assigns a single variant unconditionally). A missing or empty `cohort`
    normalises to `all`, so an unlabelled variation and one labelled `all`
    compete in the same pool and exhaust each other.
    Variations naming `portals` only apply to those portals; a portal left
    without any variant falls back to `default`.

    Supports both the current schema (`type`, plus `variants` for experiments)
    and the legacy one (`variation_type` with a `variant_id` per object). The
    audience always comes from `cohort`; legacy `conditions` strings are no
    longer honoured and a variation carrying only those counts as `all`.
    """
    portal_variants = []

    default_variations = [{
        'variation_type': 'default',
        'variant_id': 'default'
    }]
    variations = config.get('variations', default_variations)

    flattened_variations = []
    for v in variations:
        if 'variants' in v:
            for variant_config in v['variants']:
                flattened_var = {
                    'variation_type': v['type'],
                    'variant_id': variant_config['id'],
                    'percent': variant_config['percent'],
                    'cohort': normalise_cohort(v)
                }
                if 'portals' in v:
                    flattened_var['portals'] = v['portals']
                flattened_variations.append(flattened_var)
        else:
            flattened_var = {
                'variation_type': v.get('type', v.get('variation_type')),
                'variant_id': v['variant_id'],
                'cohort': normalise_cohort(v)
            }
            if 'percent' in v:
                flattened_var['percent'] = v['percent']
            if 'portals' in v:
                flattened_var['portals'] = v['portals']
            flattened_variations.append(flattened_var)

    variations = flattened_variations

    cohorts = list(set([i['cohort'] for i in variations]))

    for portal in portals:
        cohort_percs = {i: 0 for i in cohorts}
        portal_has_variant = False
        for variation in variations:
            is_portal_in_variation = not "portals" in variation or portal in variation.get('portals', [])
            is_cohort_exhausted = cohort_percs[variation['cohort']] > 99
            is_required = is_portal_in_variation and not is_cohort_exhausted
            if is_required:
                portal_variants.append(f'{portal}:{variation["variant_id"]}')
                portal_has_variant = True
                if variation["variation_type"] == "experiment":
                    cohort_percs[variation['cohort']] += variation['percent']
                else:
                    cohort_percs[variation['cohort']] = 100

        if not portal_has_variant:
            portal_variants.append(f'{portal}:default')

    return list(set(portal_variants))


def parse_path(path):
    """Parse a dot-separated override path with bracket notation into parts.

        'subfeeds.subfeed.filtering[0].params.criteria'
        -> ['subfeeds', 'subfeed', 'filtering', 0, 'params', 'criteria']
    """
    parts = []
    for part in path.split('.'):
        match = re.match(r'^(\w+)\[(\d+)\]$', part)
        if match:
            parts.append(match.group(1))
            parts.append(int(match.group(2)))
        else:
            parts.append(part)
    return parts


def resolve_overrides(obj, variant_id="default"):
    """Apply the overrides declared for `variant_id` on top of a config.

    Reads overrides from both places a variation can declare them: on the
    variation itself (matched by its `variant_id`, for a variation assigning a
    single variant) and on each entry of `variants` (matched by `id`, for one
    randomising across several). Variation-level overrides are applied first,
    so variant-level ones win where both target a path.

    A dict value is merged into a dict target, so an override can add keys to a
    `params` block without restating it; anything else replaces the target.
    Returns a new object; the input is not mutated.
    """
    obj = json.loads(json.dumps(obj))

    def apply(overrides):
        for override in overrides:
            parts = parse_path(override['path'])
            target = obj
            for part in parts[:-1]:
                target = target[part]
            if isinstance(override['value'], dict) and isinstance(target.get(parts[-1]), dict):
                target[parts[-1]] = {**target[parts[-1]], **override['value']}
            else:
                target[parts[-1]] = override['value']

    for variation in obj.get('variations', []):
        if variation.get('variant_id') == variant_id:
            apply(variation.get('overrides', []))
        for variant in variation.get('variants', []):
            if variant.get('id') == variant_id:
                apply(variant.get('overrides', []))

    return obj


def get_portal_variant_configs(config, portals):
    """Resolve a feed config into one fully resolved config per portal:variant.

        {'p1:variant_a': {...}, 'p1:default': {...}}

    Variables are resolved before overrides, so an override path targets the
    config as it looks after `$portals`/`$variants` have collapsed.
    """
    response = {}
    portal_variants = get_portal_variant_ids(config, portals)
    for i in portal_variants:
        portal, variant_id = i.split(':')
        resolved = resolve_variables(config, portal, variant_id)
        response[i] = resolve_overrides(resolved, variant_id)
    return response
