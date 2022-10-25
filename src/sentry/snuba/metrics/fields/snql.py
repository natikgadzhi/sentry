from typing import List, Optional

from snuba_sdk import Column, Function

from sentry import options
from sentry.api.utils import InvalidParams
from sentry.exceptions import InvalidSearchQuery
from sentry.models import (
    TRANSACTION_METRICS,
    ProjectTransactionThreshold,
    ProjectTransactionThresholdOverride,
)
from sentry.search.events.constants import (
    DEFAULT_PROJECT_THRESHOLD,
    DEFAULT_PROJECT_THRESHOLD_METRIC,
    MAX_QUERYABLE_TRANSACTION_THRESHOLDS,
    PROJECT_THRESHOLD_CONFIG_ALIAS,
    PROJECT_THRESHOLD_CONFIG_INDEX_ALIAS,
    PROJECT_THRESHOLD_OVERRIDE_CONFIG_INDEX_ALIAS,
)
from sentry.search.events.types import SelectType
from sentry.sentry_metrics.configuration import UseCaseKey
from sentry.sentry_metrics.utils import (
    resolve_tag_key,
    resolve_tag_value,
    resolve_tag_values,
    reverse_resolve_weak,
)
from sentry.snuba.metrics.fields.histogram import MAX_HISTOGRAM_BUCKET, zoom_histogram
from sentry.snuba.metrics.naming_layer import TransactionMRI
from sentry.snuba.metrics.naming_layer.public import (
    TransactionSatisfactionTagValue,
    TransactionStatusTagValue,
    TransactionTagsKey,
)


def _aggregation_on_session_status_func_factory(aggregate):
    def _snql_on_session_status_factory(org_id, session_status, metric_ids, alias=None):
        return Function(
            aggregate,
            [
                Column("value"),
                Function(
                    "and",
                    [
                        Function(
                            "equals",
                            [
                                Column(
                                    resolve_tag_key(
                                        UseCaseKey.RELEASE_HEALTH, org_id, "session.status"
                                    )
                                ),
                                resolve_tag_value(
                                    UseCaseKey.RELEASE_HEALTH, org_id, session_status
                                ),
                            ],
                        ),
                        Function("in", [Column("metric_id"), list(metric_ids)]),
                    ],
                ),
            ],
            alias,
        )

    return _snql_on_session_status_factory


def _counter_sum_aggregation_on_session_status_factory(
    org_id: int, session_status, metric_ids, alias=None
):
    return _aggregation_on_session_status_func_factory(aggregate="sumIf")(
        org_id, session_status, metric_ids, alias
    )


def _set_uniq_aggregation_on_session_status_factory(
    org_id: int, session_status, metric_ids, alias=None
):
    return _aggregation_on_session_status_func_factory(aggregate="uniqIf")(
        org_id, session_status, metric_ids, alias
    )


def _aggregation_on_tx_status_func_factory(aggregate):
    def _get_snql_conditions(org_id, metric_ids, exclude_tx_statuses):
        metric_match = Function("in", [Column("metric_id"), list(metric_ids)])
        assert exclude_tx_statuses is not None
        if len(exclude_tx_statuses) == 0:
            return metric_match

        tx_col = Column(
            resolve_tag_key(
                UseCaseKey.PERFORMANCE, org_id, TransactionTagsKey.TRANSACTION_STATUS.value
            )
        )
        excluded_statuses = resolve_tag_values(UseCaseKey.PERFORMANCE, org_id, exclude_tx_statuses)
        exclude_tx_statuses = Function(
            "notIn",
            [
                tx_col,
                excluded_statuses,
            ],
        )

        return Function(
            "and",
            [
                metric_match,
                exclude_tx_statuses,
            ],
        )

    def _snql_on_tx_status_factory(org_id, exclude_tx_statuses: List[str], metric_ids, alias=None):
        return Function(
            aggregate,
            [Column("value"), _get_snql_conditions(org_id, metric_ids, exclude_tx_statuses)],
            alias,
        )

    return _snql_on_tx_status_factory


def _dist_count_aggregation_on_tx_status_factory(
    org_id, exclude_tx_statuses: List[str], metric_ids, alias=None
):
    return _aggregation_on_tx_status_func_factory("countIf")(
        org_id, exclude_tx_statuses, metric_ids, alias
    )


def _aggregation_on_tx_satisfaction_func_factory(aggregate):
    def _snql_on_tx_satisfaction_factory(org_id, satisfaction_value: str, metric_ids, alias=None):
        return Function(
            aggregate,
            [
                Column("value"),
                Function(
                    "and",
                    [
                        Function(
                            "equals",
                            [
                                Column(
                                    resolve_tag_key(
                                        UseCaseKey.PERFORMANCE,
                                        org_id,
                                        TransactionTagsKey.TRANSACTION_SATISFACTION.value,
                                    )
                                ),
                                resolve_tag_value(
                                    UseCaseKey.PERFORMANCE, org_id, satisfaction_value
                                ),
                            ],
                        ),
                        Function("in", [Column("metric_id"), list(metric_ids)]),
                    ],
                ),
            ],
            alias,
        )

    return _snql_on_tx_satisfaction_factory


def _dist_count_aggregation_on_tx_satisfaction_factory(
    org_id, satisfaction: str, metric_ids, alias=None
):
    return _aggregation_on_tx_satisfaction_func_factory("countIf")(
        org_id, satisfaction, metric_ids, alias
    )


def _set_count_aggregation_on_tx_satisfaction_factory(
    org_id, satisfaction: str, metric_ids, alias=None
):
    return _aggregation_on_tx_satisfaction_func_factory("uniqIf")(
        org_id=org_id, satisfaction_value=satisfaction, metric_ids=metric_ids, alias=alias
    )


def all_sessions(org_id: int, metric_ids, alias=None):
    return _counter_sum_aggregation_on_session_status_factory(
        org_id, session_status="init", metric_ids=metric_ids, alias=alias
    )


def all_users(org_id: int, metric_ids, alias=None):
    return uniq_aggregation_on_metric(metric_ids, alias)


def crashed_sessions(org_id: int, metric_ids, alias=None):
    return _counter_sum_aggregation_on_session_status_factory(
        org_id, session_status="crashed", metric_ids=metric_ids, alias=alias
    )


def crashed_users(org_id: int, metric_ids, alias=None):
    return _set_uniq_aggregation_on_session_status_factory(
        org_id, session_status="crashed", metric_ids=metric_ids, alias=alias
    )


def errored_preaggr_sessions(org_id: int, metric_ids, alias=None):
    return _counter_sum_aggregation_on_session_status_factory(
        org_id, session_status="errored_preaggr", metric_ids=metric_ids, alias=alias
    )


def abnormal_sessions(org_id: int, metric_ids, alias=None):
    return _counter_sum_aggregation_on_session_status_factory(
        org_id, session_status="abnormal", metric_ids=metric_ids, alias=alias
    )


def abnormal_users(org_id: int, metric_ids, alias=None):
    return _set_uniq_aggregation_on_session_status_factory(
        org_id, session_status="abnormal", metric_ids=metric_ids, alias=alias
    )


def errored_all_users(org_id: int, metric_ids, alias=None):
    return _set_uniq_aggregation_on_session_status_factory(
        org_id, session_status="errored", metric_ids=metric_ids, alias=alias
    )


def uniq_aggregation_on_metric(metric_ids, alias=None):
    return Function(
        "uniqIf",
        [
            Column("value"),
            Function(
                "in",
                [
                    Column("metric_id"),
                    list(metric_ids),
                ],
            ),
        ],
        alias,
    )


def all_transactions(org_id, metric_ids, alias=None):
    return _dist_count_aggregation_on_tx_status_factory(
        org_id,
        exclude_tx_statuses=[],
        metric_ids=metric_ids,
        alias=alias,
    )


def failure_count_transaction(org_id, metric_ids, alias=None):
    return _dist_count_aggregation_on_tx_status_factory(
        org_id,
        exclude_tx_statuses=[
            # See statuses in https://docs.sentry.io/product/performance/metrics/#failure-rate
            TransactionStatusTagValue.OK.value,
            TransactionStatusTagValue.CANCELLED.value,
            TransactionStatusTagValue.UNKNOWN.value,
        ],
        metric_ids=metric_ids,
        alias=alias,
    )


def satisfaction_count_transaction(org_id, metric_ids, alias=None):
    metric_ids_dictionary = {
        reverse_resolve_weak(UseCaseKey.PERFORMANCE, org_id, metric_id): metric_id
        for metric_id in metric_ids
    }

    return Function(
        "countIf",
        [
            Column("value"),
            Function(
                "and",
                [
                    Function(
                        "equals",
                        [
                            Column("metric_id"),
                            Function(
                                "multiIf",
                                [
                                    Function(
                                        "equals",
                                        [
                                            _resolve_project_threshold_config(
                                                org_id, [4550644461469697]
                                            ),
                                            "lcp",
                                        ],
                                    ),
                                    metric_ids_dictionary[TransactionMRI.MEASUREMENTS_LCP.value],
                                    metric_ids_dictionary[TransactionMRI.DURATION.value],
                                ],
                            ),
                        ],
                    )
                ],
            ),
        ],
    )


def tolerated_count_transaction(org_id, metric_ids, alias=None):
    return _dist_count_aggregation_on_tx_satisfaction_factory(
        org_id, TransactionSatisfactionTagValue.TOLERATED.value, metric_ids, alias
    )


def apdex(satisfactory_snql, tolerable_snql, total_snql, alias=None):
    return division_float(
        arg1_snql=addition(satisfactory_snql, division_float(tolerable_snql, 2)),
        arg2_snql=total_snql,
        alias=alias,
    )


def miserable_users(org_id, metric_ids, alias=None):
    return _set_count_aggregation_on_tx_satisfaction_factory(
        org_id=org_id,
        satisfaction=TransactionSatisfactionTagValue.FRUSTRATED.value,
        metric_ids=metric_ids,
        alias=alias,
    )


def subtraction(arg1_snql, arg2_snql, alias=None):
    return Function("minus", [arg1_snql, arg2_snql], alias)


def addition(arg1_snql, arg2_snql, alias=None):
    return Function("plus", [arg1_snql, arg2_snql], alias)


def division_float(arg1_snql, arg2_snql, alias=None):
    return Function(
        "divide",
        # Clickhouse can manage divisions by 0, see:
        # https://clickhouse.com/docs/en/sql-reference/functions/arithmetic-functions/#dividea-b-a-b-operator
        [arg1_snql, arg2_snql],
        alias=alias,
    )


def complement(arg1_snql, alias=None):
    """(x) -> (1 - x)"""
    return Function("minus", [1.0, arg1_snql], alias=alias)


def session_duration_filters(org_id):
    return [
        Function(
            "equals",
            (
                Column(resolve_tag_key(UseCaseKey.RELEASE_HEALTH, org_id, "session.status")),
                resolve_tag_value(UseCaseKey.RELEASE_HEALTH, org_id, "exited"),
            ),
        )
    ]


def histogram_snql_factory(
    aggregate_filter,
    histogram_from: Optional[float] = None,
    histogram_to: Optional[float] = None,
    histogram_buckets: int = 100,
    alias=None,
):
    zoom_conditions = zoom_histogram(
        histogram_buckets=histogram_buckets,
        histogram_from=histogram_from,
        histogram_to=histogram_to,
    )
    if zoom_conditions is not None:
        conditions = Function("and", [zoom_conditions, aggregate_filter])
    else:
        conditions = aggregate_filter

    return Function(
        f"histogramIf({MAX_HISTOGRAM_BUCKET})",
        [Column("value"), conditions],
        alias=alias,
    )


def rate_snql_factory(aggregate_filter, numerator, denominator=1.0, alias=None):
    return Function(
        "divide",
        [
            Function("countIf", [Column("value"), aggregate_filter]),
            Function("divide", [numerator, denominator]),
        ],
        alias=alias,
    )


def count_web_vitals_snql_factory(aggregate_filter, org_id, measurement_rating, alias=None):
    return Function(
        "countIf",
        [
            Column("value"),
            Function(
                "and",
                [
                    aggregate_filter,
                    Function(
                        "equals",
                        (
                            Column(
                                resolve_tag_key(
                                    UseCaseKey.PERFORMANCE, org_id, "measurement_rating"
                                )
                            ),
                            resolve_tag_value(UseCaseKey.PERFORMANCE, org_id, measurement_rating),
                        ),
                    ),
                ],
            ),
        ],
        alias=alias,
    )


def count_transaction_name_snql_factory(aggregate_filter, org_id, transaction_name, alias=None):
    is_unparameterized = "is_unparameterized"
    is_null = "is_null"
    has_value = "has_value"

    def generate_transaction_name_filter(operation, transaction_name_identifier):
        if transaction_name_identifier == is_unparameterized:
            inner_tag_value = resolve_tag_value(
                UseCaseKey.PERFORMANCE, org_id, "<< unparameterized >>"
            )
        elif transaction_name_identifier == is_null:
            inner_tag_value = (
                "" if options.get("sentry-metrics.performance.tags-values-are-strings") else 0
            )
        else:
            raise InvalidParams("Invalid condition for tag value filter")

        return Function(
            operation,
            [
                Column(
                    resolve_tag_key(
                        UseCaseKey.PERFORMANCE,
                        org_id,
                        "transaction",
                    )
                ),
                inner_tag_value,
            ],
        )

    if transaction_name in [is_unparameterized, is_null]:
        transaction_name_filter = generate_transaction_name_filter("equals", transaction_name)
    elif transaction_name == has_value:
        transaction_name_filter = Function(
            "and",
            [
                generate_transaction_name_filter("notEquals", is_null),
                generate_transaction_name_filter("notEquals", is_unparameterized),
            ],
        )
    else:
        raise InvalidParams(
            f"The `count_transaction_name` function expects a valid transaction name filter, which must be either "
            f"{is_unparameterized} {is_null} {has_value} but {transaction_name} was passed"
        )

    return Function(
        "countIf",
        [
            Column("value"),
            Function(
                "and",
                [aggregate_filter, transaction_name_filter],
            ),
        ],
        alias=alias,
    )


def team_key_transaction_snql(org_id, team_key_condition_rhs, alias=None):
    team_key_conditions = set()
    for elem in team_key_condition_rhs:
        if len(elem) != 2:
            raise InvalidParams("Invalid team_key_condition in params")

        project_id, transaction_name = elem
        team_key_conditions.add(
            (project_id, resolve_tag_value(UseCaseKey.PERFORMANCE, org_id, transaction_name))
        )

    return Function(
        "in",
        [
            (
                Column("project_id"),
                Column(resolve_tag_key(UseCaseKey.PERFORMANCE, org_id, "transaction")),
            ),
            list(team_key_conditions),
        ],
        alias=alias,
    )


def _resolve_project_threshold_config(org_id, project_ids):
    project_threshold_configs = (
        ProjectTransactionThreshold.objects.filter(
            organization_id=org_id,
            project_id__in=project_ids,
        )
        .order_by("project_id")
        .values_list("project_id", "threshold", "metric")
    )

    transaction_threshold_configs = (
        ProjectTransactionThresholdOverride.objects.filter(
            organization_id=org_id,
            project_id__in=project_ids,
        )
        .order_by("project_id")
        .values_list("transaction", "project_id", "threshold", "metric")
    )

    num_project_thresholds = project_threshold_configs.count()
    num_transaction_thresholds = transaction_threshold_configs.count()

    if num_project_thresholds + num_transaction_thresholds > MAX_QUERYABLE_TRANSACTION_THRESHOLDS:
        raise InvalidSearchQuery(
            f"Exceeded {MAX_QUERYABLE_TRANSACTION_THRESHOLDS} configured transaction thresholds limit, try with fewer Projects."
        )

    # Arrays need to have toUint64 casting because clickhouse will define the type as the narrowest possible type
    # that can store listed argument types, which means the comparison will fail because of mismatched types
    project_thresholds = {}
    project_threshold_config_keys = []
    project_threshold_config_values = []
    for project_ids, threshold, metric in project_threshold_configs:
        metric = TRANSACTION_METRICS[metric]
        if threshold == DEFAULT_PROJECT_THRESHOLD and metric == DEFAULT_PROJECT_THRESHOLD_METRIC:
            # small optimization, if the configuration is equal to the default,
            # we can skip it in the final query
            continue

        project_thresholds[project_ids] = (metric, threshold)
        project_threshold_config_keys.append(Function("toUInt64", [project_ids]))
        project_threshold_config_values.append((metric, threshold))

    project_threshold_override_config_keys = []
    project_threshold_override_config_values = []
    for transaction, project_ids, threshold, metric in transaction_threshold_configs:
        metric = TRANSACTION_METRICS[metric]
        if (
            project_ids in project_thresholds
            and threshold == project_thresholds[project_ids][1]
            and metric == project_thresholds[project_ids][0]
        ):
            # small optimization, if the configuration is equal to the project
            # configs, we can skip it in the final query
            continue

        elif (
            project_ids not in project_thresholds
            and threshold == DEFAULT_PROJECT_THRESHOLD
            and metric == DEFAULT_PROJECT_THRESHOLD_METRIC
        ):
            # small optimization, if the configuration is equal to the default
            # and no project configs were set, we can skip it in the final query
            continue

        project_threshold_override_config_keys.append(
            (Function("toUInt64", [project_ids]), transaction)
        )
        project_threshold_override_config_values.append((metric, threshold))

    project_threshold_config_index: SelectType = Function(
        "indexOf",
        [
            project_threshold_config_keys,
            Column(name="project_id"),
        ],
        PROJECT_THRESHOLD_CONFIG_INDEX_ALIAS,
    )

    project_threshold_override_config_index: SelectType = Function(
        "indexOf",
        [
            project_threshold_override_config_keys,
            (
                Column(name="project_id"),
                Column(name=resolve_tag_key(UseCaseKey.PERFORMANCE, org_id, "transaction")),
            ),
        ],
        PROJECT_THRESHOLD_OVERRIDE_CONFIG_INDEX_ALIAS,
    )

    def _project_threshold_config(alias: Optional[str] = None) -> SelectType:
        if project_threshold_config_keys and project_threshold_config_values:
            return Function(
                "if",
                [
                    Function(
                        "equals",
                        [
                            project_threshold_config_index,
                            0,
                        ],
                    ),
                    (DEFAULT_PROJECT_THRESHOLD_METRIC, DEFAULT_PROJECT_THRESHOLD),
                    Function(
                        "arrayElement",
                        [
                            project_threshold_config_values,
                            project_threshold_config_index,
                        ],
                    ),
                ],
                alias,
            )

        return Function(
            "tuple",
            [DEFAULT_PROJECT_THRESHOLD_METRIC, DEFAULT_PROJECT_THRESHOLD],
            alias,
        )

    if project_threshold_override_config_keys and project_threshold_override_config_values:
        return Function(
            "if",
            [
                Function(
                    "equals",
                    [
                        project_threshold_override_config_index,
                        0,
                    ],
                ),
                _project_threshold_config(),
                Function(
                    "arrayElement",
                    [
                        project_threshold_override_config_values,
                        project_threshold_override_config_index,
                    ],
                ),
            ],
            PROJECT_THRESHOLD_CONFIG_ALIAS,
        )

    return _project_threshold_config(PROJECT_THRESHOLD_CONFIG_ALIAS)
