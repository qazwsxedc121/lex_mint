import { describe, expect, it } from 'vitest';
import { ragConfig } from '../../../../../src/modules/settings/config/rag.config';

describe('ragConfig', () => {
  it('strips UI-only retrieval preset before save', () => {
    const payload = ragConfig.transformSave?.({
      retrieval_preset: 'balanced',
      top_k: 5,
      score_threshold: 0.3,
    });

    expect(payload).toEqual({
      top_k: 5,
      score_threshold: 0.3,
    });
  });

  it('defines retrieval preset effects for fast, balanced, and deep modes', () => {
    const presetField = ragConfig.fields.find(
      (field) => field.type === 'preset' && field.name === 'retrieval_preset'
    );

    expect(presetField).toBeDefined();
    expect(presetField?.options).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          value: 'fast',
          effects: expect.objectContaining({ top_k: 3, recall_k: 10 }),
        }),
        expect.objectContaining({
          value: 'balanced',
          effects: expect.objectContaining({ top_k: 5, recall_k: 20 }),
        }),
        expect.objectContaining({
          value: 'deep',
          effects: expect.objectContaining({ top_k: 10, recall_k: 50 }),
        }),
      ])
    );
  });
});
