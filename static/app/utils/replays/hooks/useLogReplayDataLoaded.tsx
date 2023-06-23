import {useEffect} from 'react';

import {trackAnalytics} from 'sentry/utils/analytics';
import type useReplayData from 'sentry/utils/replays/hooks/useReplayData';
import useOrganization from 'sentry/utils/useOrganization';
import useProjectFromSlug from 'sentry/utils/useProjectFromSlug';

interface Props
  extends Pick<
    ReturnType<typeof useReplayData>,
    'fetchError' | 'fetching' | 'projectSlug' | 'replay'
  > {}

function useLogReplayDataLoaded({fetchError, fetching, projectSlug, replay}: Props) {
  const organization = useOrganization();
  const project = useProjectFromSlug({
    organization,
    projectSlug: projectSlug ?? undefined,
  });

  useEffect(() => {
    if (fetching || fetchError || !replay || !project) {
      return;
    }

    const errorFrames = replay.getErrorFrames();
    const feErrors = errorFrames.filter(frame => frame.data.projectSlug === projectSlug);
    const beErrors = errorFrames.filter(frame => frame.data.projectSlug !== projectSlug);

    trackAnalytics('replay.details-data-loaded', {
      organization,
      be_errors: beErrors.length,
      fe_errors: feErrors.length,
      project_platform: project.platform!,
      replay_errors: 0,
      total_errors: errorFrames.length,
      started_at_delta: replay.timestampDeltas.startedAtDelta,
      finished_at_delta: replay.timestampDeltas.finishedAtDelta,
      replay_id: replay.getReplay().id,
    });
  }, [organization, project, fetchError, fetching, projectSlug, replay]);
}

export default useLogReplayDataLoaded;
