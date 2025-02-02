import BaseAvatar from 'sentry/components/avatar/baseAvatar';
import type {Team} from 'sentry/types';
import {explodeSlug} from 'sentry/utils';

interface TeamAvatarProps extends Omit<BaseAvatar['props'], 'uploadPath' | 'uploadId'> {
  team: Team | null | undefined;
}

function TeamAvatar({team, tooltip: tooltipProp, ...props}: TeamAvatarProps) {
  if (!team) {
    return null;
  }

  const slug = (team && team.slug) || '';
  const title = explodeSlug(slug);
  const tooltip = tooltipProp ?? `#${title}`;

  return (
    <BaseAvatar
      {...props}
      type={(team.avatar && team.avatar.avatarType) || 'letter_avatar'}
      uploadPath="team-avatar"
      uploadId={team.avatar && team.avatar.avatarUuid}
      letterId={slug}
      tooltip={tooltip}
      title={title}
    />
  );
}

export default TeamAvatar;
