import pytest

from chm_utils.feed_configs import (
    get_portal_variant_configs,
    get_portal_variant_ids,
    parse_path,
    resolve_overrides,
    resolve_variables,
)


# --- variable resolution -----------------------------------------------------

def test_resolve_variables_in_lists_and_dicts():
    config = {
        "list": [{"$variants": {"a_1": 1, "a_2": 2, "b_1": 3}}, 4],
        "dict": {
            "sub_dict": {"$variants": {"a_1": 1, "default": 4}},
            "random": 5,
        },
        "matching_key": {"$variants": {"a_*": 6, "b_1": 7}},
    }

    resolved = resolve_variables(config, 'p1', 'a_1')
    assert resolved["list"] == [1, 4]
    assert resolved["dict"] == {"sub_dict": 1, "random": 5}
    assert resolved["matching_key"] == 6

    resolved = resolve_variables(config, 'p1', 'b_1')
    assert resolved["list"] == [3, 4]
    assert resolved["dict"] == {"sub_dict": 4, "random": 5}
    assert resolved["matching_key"] == 7


def test_resolve_variables_does_not_mutate_original():
    config = {"section": {"$variants": {"a_1": 1, "default": 2}}}

    resolve_variables(config, 'p1', 'a_1')

    assert config["section"] == {"$variants": {"a_1": 1, "default": 2}}


def test_exact_variant_match_beats_pattern():
    config = {
        "content": {
            "$variants": {
                "a_*": "pattern content",
                "a_p1_1": "exact content",
                "a_p1_*": "specific pattern content",
                "default": "default content",
            }
        }
    }

    assert resolve_variables(config, 'p1', 'a_p1_1')["content"] == "exact content"


def test_longest_variant_pattern_wins():
    """The longest matching pattern is assumed to be the most specific one."""
    config = {
        "content": {
            "$variants": {
                "a_*": "general content",
                "a_p1_*": "p1 content",
                "default": "default content",
            }
        }
    }

    assert resolve_variables(config, 'p1', 'a_p1_1')["content"] == "p1 content"
    assert resolve_variables(config, 'p1', 'a_other')["content"] == "general content"
    assert resolve_variables(config, 'p1', 'unknown')["content"] == "default content"


def test_resolve_portals():
    config = {"content": {"$portals": {"p1": "p1 content", "default": "default content"}}}

    assert resolve_variables(config, 'p1', 'any')["content"] == "p1 content"
    assert resolve_variables(config, 'unknown', 'any')["content"] == "default content"


def test_variable_siblings_survive_resolution():
    config = {"score_a": {"$variants": {"a_1": {"window": "24h"}}, "metric": "m1"}}

    assert resolve_variables(config, 'p1', 'a_1')["score_a"] == {"window": "24h", "metric": "m1"}


def test_unresolvable_variable_raises():
    config = {"content": {"$variants": {"a_1": 1}}}

    with pytest.raises(Exception, match="could not be resolved"):
        resolve_variables(config, 'p1', 'a_2')


# --- portal:variant enumeration ----------------------------------------------

def test_portal_variants_without_variations():
    assert sorted(get_portal_variant_ids({}, ['p1', 'p2'])) == ['p1:default', 'p2:default']


def test_single_variant_variation_covers_portals_the_experiment_excludes():
    """A portal outside the experiment's portals still gets the cohort's variant."""
    config = {'variations': [
        {"type": "experiment", "id": "exp-1", "cohort": "subs",
         "portals": ["p2", "p3"],
         "variants": [{"id": "a_1", "percent": 50}, {"id": "a_2", "percent": 50}]},
        {"type": "segmentation", "id": "seg-1", "cohort": "subs", "variant_id": "a_2"},
        {"type": "default", "variant_id": "default"},
    ]}

    variants = get_portal_variant_configs(config, ['p1', 'p2', 'p3'])

    assert 'p1:a_2' in variants
    assert 'p1:a_1' not in variants


def test_exhausted_cohort_drops_later_variations():
    """Two 50% experiment variants fill the cohort, so the segmentation is dropped."""
    config = {'variations': [
        {"variation_type": "experiment", "experiment_id": "exp-1", "cohort": "subs",
         "portals": ["p2", "p3"], "percent": 50, "variant_id": "a_1"},
        {"variation_type": "experiment", "experiment_id": "exp-1", "cohort": "subs",
         "portals": ["p2", "p3"], "percent": 50, "variant_id": "a_2"},
        {"variation_type": "segmentation", "cohort": "subs", "variant_id": "a_3"},
        {"variation_type": "default", "variant_id": "default"},
    ]}

    variants = get_portal_variant_configs(config, ['p1', 'p2', 'p3'])

    assert 'p1:a_3' in variants
    assert 'p3:a_3' not in variants


def test_cohort_allocation_is_order_dependent():
    """A 100% variation first exhausts the cohort for every portal it covers."""
    config = {'variations': [
        {"variation_type": "experiment", "experiment_id": "exp-2", "cohort": "subs",
         "percent": 100, "variant_id": "a_3"},
        {"variation_type": "experiment", "experiment_id": "exp-1", "cohort": "subs",
         "portals": ["p2", "p3"], "percent": 50, "variant_id": "a_1"},
        {"variation_type": "experiment", "experiment_id": "exp-1", "cohort": "subs",
         "portals": ["p2", "p3"], "percent": 50, "variant_id": "a_2"},
        {"variation_type": "default", "variant_id": "default"},
    ]}

    variants = get_portal_variant_configs(config, ['p1', 'p2', 'p3'])

    assert 'p3:a_3' in variants
    assert 'p2:a_1' not in variants


def test_cohorts_have_independent_allocation():
    """A full experiment in one cohort leaves another cohort's variations intact."""
    config = {'variations': [
        {"type": "experiment", "id": "exp-1", "cohort": "subs",
         "variants": [{"id": "subs_a", "percent": 50}, {"id": "subs_b", "percent": 50}]},
        {"type": "experiment", "id": "exp-2", "cohort": "nonsubs",
         "variants": [{"id": "nonsubs_a", "percent": 50}, {"id": "nonsubs_b", "percent": 50}]},
    ]}

    variants = get_portal_variant_ids(config, ['p1'])

    assert sorted(variants) == ['p1:nonsubs_a', 'p1:nonsubs_b', 'p1:subs_a', 'p1:subs_b']


def test_portal_outside_any_variation_gets_default():
    config = {
        'variations': [
            {"type": "experiment", "id": "exp-1", "randomize": "session",
             "portals": ["p1"],
             "variants": [{"id": "a_1", "percent": 50}, {"id": "a_2", "percent": 50}]}
        ],
        'subfeeds': {'main': {'sorting': {'formula': {
            '$variants': {'default': '{score_a}', 'a_2': '{score_a} + {score_b}'}
        }}}},
    }

    variants = get_portal_variant_configs(config, ['p1', 'p2'])

    assert 'p1:a_1' in variants
    assert 'p1:a_2' in variants
    assert 'p2:default' in variants
    assert 'p2:a_1' not in variants
    assert variants['p2:default']['subfeeds']['main']['sorting']['formula'] == '{score_a}'


# --- override paths ----------------------------------------------------------

def test_parse_path():
    assert parse_path('subfeeds.main.sorting.formula') == ['subfeeds', 'main', 'sorting', 'formula']
    assert parse_path('subfeeds.main.filtering[0].params') == ['subfeeds', 'main', 'filtering', 0, 'params']
    assert parse_path('a[0].b[12].c') == ['a', 0, 'b', 12, 'c']


# --- variant-level overrides -------------------------------------------------

def multi_variant_config(overrides):
    """A variation randomising across variants declares overrides per variant."""
    return {
        "variations": [
            {"type": "experiment", "id": "exp-1", "variants": [
                {"id": "a_1", "percent": 50},
                {"id": "a_2", "percent": 50, "overrides": overrides},
            ]}
        ],
        "subfeeds": {"main": {
            "sorting": {"formula": "default_formula"},
            "scoring": {"score_a": {"params": {"metric": "m1", "window": "auto"}}},
            "filtering": [
                {"filter_type": "f1", "params": {"criteria": "old_criteria"}},
                {"filter_type": "f2"},
            ],
        }},
    }


def test_variant_overrides_apply_only_to_their_variant():
    config = multi_variant_config([{"path": "subfeeds.main.sorting.formula", "value": "new_formula"}])

    assert resolve_overrides(config, "a_2")["subfeeds"]["main"]["sorting"]["formula"] == "new_formula"
    assert resolve_overrides(config, "a_1")["subfeeds"]["main"]["sorting"]["formula"] == "default_formula"


def test_overrides_do_not_mutate_original():
    config = multi_variant_config([{"path": "subfeeds.main.sorting.formula", "value": "new_formula"}])

    resolve_overrides(config, "a_2")

    assert config["subfeeds"]["main"]["sorting"]["formula"] == "default_formula"


def test_override_targets_list_index():
    config = multi_variant_config([
        {"path": "subfeeds.main.filtering[0].params.criteria", "value": "new_criteria"}
    ])

    resolved = resolve_overrides(config, "a_2")

    assert resolved["subfeeds"]["main"]["filtering"][0]["params"]["criteria"] == "new_criteria"
    assert resolved["subfeeds"]["main"]["filtering"][1]["filter_type"] == "f2"


def test_multiple_overrides_all_apply():
    config = multi_variant_config([
        {"path": "subfeeds.main.sorting.formula", "value": "f1"},
        {"path": "subfeeds.main.scoring.score_a.params.metric", "value": "m2"},
    ])

    resolved = resolve_overrides(config, "a_2")

    assert resolved["subfeeds"]["main"]["sorting"]["formula"] == "f1"
    assert resolved["subfeeds"]["main"]["scoring"]["score_a"]["params"]["metric"] == "m2"


def test_dict_override_merges_into_dict_target():
    config = multi_variant_config([
        {"path": "subfeeds.main.scoring.score_a.params", "value": {"extra": "auto"}}
    ])

    params = resolve_overrides(config, "a_2")["subfeeds"]["main"]["scoring"]["score_a"]["params"]

    assert params == {"metric": "m1", "window": "auto", "extra": "auto"}


def test_non_dict_override_replaces_target():
    config = multi_variant_config([{"path": "subfeeds.main.scoring.score_a.params", "value": None}])

    assert resolve_overrides(config, "a_2")["subfeeds"]["main"]["scoring"]["score_a"]["params"] is None


# --- variation-level overrides -----------------------------------------------

def single_variant_config(overrides):
    """A variation assigning one variant declares overrides on itself."""
    return {
        "portals": ["p1"],
        "variations": [
            {"type": "segmentation", "variant_id": "a_1", "cohort": "subs",
             "overrides": overrides},
            {"type": "default", "variant_id": "default"},
        ],
        "subfeeds": {"main": {
            "scoring": {"score_a": {"params": {"window": "48h"}}},
            "sorting": {"blends": [{"id": "blend_a"}]},
        }},
    }


def test_variation_level_overrides_apply_to_their_variant():
    """The variation assigns a single variant, so its overrides sit on the variation."""
    config = single_variant_config([
        {"path": "subfeeds.main.scoring.score_a.params.window", "value": "24h"}
    ])

    resolved = resolve_overrides(config, "a_1")

    assert resolved["subfeeds"]["main"]["scoring"]["score_a"]["params"]["window"] == "24h"


def test_variation_level_overrides_skip_other_variants():
    config = single_variant_config([
        {"path": "subfeeds.main.scoring.score_a.params.window", "value": "24h"}
    ])

    resolved = resolve_overrides(config, "default")

    assert resolved["subfeeds"]["main"]["scoring"]["score_a"]["params"]["window"] == "48h"


def test_variation_level_overrides_resolve_end_to_end():
    config = single_variant_config([
        {"path": "subfeeds.main.scoring.score_a.params.window", "value": "24h"},
        {"path": "subfeeds.main.sorting", "value": {"blends": [{"id": "blend_b"}]}},
    ])

    configs = get_portal_variant_configs(config, config["portals"])

    assert sorted(configs) == ['p1:a_1', 'p1:default']
    variant, default = configs['p1:a_1']['subfeeds']['main'], configs['p1:default']['subfeeds']['main']
    assert variant['scoring']['score_a']['params']['window'] == "24h"
    assert variant['sorting']['blends'] == [{"id": "blend_b"}]
    assert default['scoring']['score_a']['params']['window'] == "48h"
    assert default['sorting']['blends'] == [{"id": "blend_a"}]


def test_variant_level_overrides_win_over_variation_level():
    """Both levels target the same path; the more specific variant-level one lands last."""
    config = {
        "variations": [
            {"type": "experiment", "id": "exp-1", "variant_id": "a_2",
             "overrides": [{"path": "subfeeds.main.sorting.formula", "value": "shared"}],
             "variants": [
                 {"id": "a_2", "percent": 50,
                  "overrides": [{"path": "subfeeds.main.sorting.formula", "value": "variant"}]},
             ]}
        ],
        "subfeeds": {"main": {"sorting": {"formula": "base"}}},
    }

    assert resolve_overrides(config, "a_2")["subfeeds"]["main"]["sorting"]["formula"] == "variant"


def test_overrides_apply_after_variables_are_resolved():
    """An override path targets the config as it looks once $variants have collapsed."""
    config = {
        "portals": ["p1"],
        "variations": [
            {"type": "segmentation", "variant_id": "a_1", "cohort": "subs",
             "overrides": [{"path": "subfeeds.main.scoring.params.scaling", "value": 0.9}]},
            {"type": "default", "variant_id": "default"},
        ],
        "subfeeds": {"main": {"scoring": {
            "$variants": {
                "a_1": {"params": {"scaling": 0.5, "metric": "m1"}},
                "default": {"params": {"scaling": 0.1}},
            }
        }}},
    }

    configs = get_portal_variant_configs(config, config["portals"])

    assert configs['p1:a_1']['subfeeds']['main']['scoring']['params'] == {"scaling": 0.9, "metric": "m1"}
    assert configs['p1:default']['subfeeds']['main']['scoring']['params'] == {"scaling": 0.1}
