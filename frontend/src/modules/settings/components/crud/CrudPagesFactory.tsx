/**
 * CrudPagesFactory
 *
 * Generates create/edit pages for CRUD configs to reduce boilerplate.
 */

import React from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CrudCreatePage } from './CrudCreatePage';
import { CrudEditPage } from './CrudEditPage';
import { ErrorMessage } from '../common';
import type { CrudSettingsConfig, CrudHook, ConfigContext } from '../../config/types';

interface CrudPagesFactoryOptions<T> {
  config: CrudSettingsConfig<T>;
  useData: () => {
    hook: CrudHook<T>;
    context?: ConfigContext;
    getItemId?: (item: T) => string;
  };
  backPath: string;
  idParam: string;
  decodeId?: (raw: string) => string;
  missingMessage?: string;
}

export function makeCrudPages<T>(options: CrudPagesFactoryOptions<T>) {
  const CreatePage: React.FC = () => {
    const { hook, context } = options.useData();
    return (
      <CrudCreatePage
        config={options.config}
        hook={hook}
        context={context}
        backPath={options.backPath}
      />
    );
  };

  const EditPage: React.FC = () => {
    const { hook, context, getItemId } = options.useData();
    const params = useParams();
    const rawId = params[options.idParam];
    const { t } = useTranslation('settings');

    if (!rawId) {
      return (
        <ErrorMessage
          message={options.missingMessage || t('crud.notFound', { item: options.config.itemName })}
          onRetry={hook.refreshData}
        />
      );
    }

    const itemId = options.decodeId ? options.decodeId(rawId) : rawId;

    return (
      <CrudEditPage
        config={options.config}
        hook={hook}
        itemId={itemId}
        context={context}
        getItemId={getItemId}
        backPath={options.backPath}
      />
    );
  };

  return { CreatePage, EditPage };
}
