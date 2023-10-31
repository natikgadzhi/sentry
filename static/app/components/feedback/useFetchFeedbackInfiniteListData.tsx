import {useCallback, useMemo} from 'react';
import {Index, IndexRange} from 'react-virtualized';

import useFeedbackListQueryKey from 'sentry/components/feedback/useFeedbackListQueryKey';
import {FeedbackIssueList} from 'sentry/utils/feedback/types';
import {useInfiniteApiQuery} from 'sentry/utils/queryClient';
import useOrganization from 'sentry/utils/useOrganization';

export const EMPTY_INFINITE_LIST_DATA: ReturnType<
  typeof useFetchFeedbackInfiniteListData
> = {
  error: null,
  hasNextPage: false,
  isError: false,
  isFetching: false, // If the network is active
  isFetchingNextPage: false,
  isFetchingPreviousPage: false,
  isLoading: false, // If anything is loaded yet
  // Below are fields that are shims for react-virtualized
  getRow: () => undefined,
  isRowLoaded: () => false,
  issues: [],
  loadMoreRows: () => Promise.resolve(),
};

export default function useFetchFeedbackInfiniteListData() {
  const organization = useOrganization();
  const queryKey = useFeedbackListQueryKey({organization});
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isError,
    isFetching, // If the network is active
    isFetchingNextPage,
    isFetchingPreviousPage,
    isLoading, // If anything is loaded yet
  } = useInfiniteApiQuery<FeedbackIssueList>({queryKey});

  const issues = useMemo(
    () => data?.pages.flatMap(([pageData]) => pageData) ?? [],
    [data]
  );

  const getRow = useCallback(
    ({index}: Index): FeedbackIssueList[number] | undefined => issues?.[index],
    [issues]
  );

  const isRowLoaded = useCallback(({index}: Index) => Boolean(issues?.[index]), [issues]);

  const loadMoreRows = useCallback(
    ({startIndex: _1, stopIndex: _2}: IndexRange) =>
      hasNextPage && !isFetching ? fetchNextPage() : Promise.resolve(),
    [hasNextPage, isFetching, fetchNextPage]
  );

  return {
    error,
    hasNextPage,
    isError,
    isFetching, // If the network is active
    isFetchingNextPage,
    isFetchingPreviousPage,
    isLoading, // If anything is loaded yet
    // Below are fields that are shims for react-virtualized
    getRow,
    isRowLoaded,
    issues,
    loadMoreRows,
  };
}
