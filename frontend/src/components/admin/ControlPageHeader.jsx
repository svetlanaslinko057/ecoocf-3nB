/**
 * ControlPageHeader — thin wrapper that delegates to AdminPageHeader.
 *
 * Why this exists: a number of admin "Control"-family pages were built
 * before the platform standardised on `<AdminPageHeader>`. Rather than
 * refactor each call-site, this component preserves the original API
 * (`icon`, `title`, `subtitle`, `action`, `iconColor`, `testId`) and
 * renders the canonical mobile-first header underneath, so every page
 * using `<ControlPageHeader>` automatically gets the unified look.
 */
import React from 'react';
import { AdminPageHeader } from '../ui/AdminPagePrimitives';

const ControlPageHeader = ({
  icon,
  title,
  subtitle,
  action,
  testId,
  // iconColor — silently ignored; AdminPageHeader uses the platform palette.
}) => (
  <AdminPageHeader
    icon={icon}
    title={title}
    subtitle={subtitle}
    actions={action}
    testId={testId || 'control-page-header'}
  />
);

export default ControlPageHeader;
