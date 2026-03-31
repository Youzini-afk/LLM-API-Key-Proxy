// ============================================================
// Channels Page — 渠道管理（可读 + 可管）
// ============================================================
import { h, clearChildren, icon } from '../utils/dom.js';
import { api } from '../api.js';
import { formatNumber, formatTokens } from '../utils/format.js';
import { KeyTable } from '../components/ui.js';
import { showToast } from '../components/toast.js';

const PROVIDER_OPTIONS = [
  { value: 'openai_compatible', label: 'OpenAI Compatible' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: '__custom__', label: '自定义...' },
];

function modelsToPairs(models) {
  const pairs = [];
  const data = models || {};
  Object.entries(data).forEach(([k, v]) => {
    if (typeof v === 'string') pairs.push({ key: k, value: v });
    else if (v && typeof v === 'object' && v.id) pairs.push({ key: k, value: v.id });
  });
  return pairs;
}

function pairsToModels(pairs) {
  const result = {};
  (pairs || []).forEach((p) => {
    const k = (p.key || '').trim();
    const v = (p.value || '').trim();
    if (!k || !v) return;
    result[k] = { id: v };
  });
  return result;
}

function inferTemplateByUrl(url) {
  const u = (url || '').toLowerCase();
  if (u.includes('infini-ai.com')) {
    return [
      { key: '[喵喵] kimi-k2.5', value: 'kimi-k2.5' },
      { key: '[喵喵] glm-5', value: 'glm-5' },
      { key: '[喵喵] qwen3.5-plus', value: 'qwen3.5-plus' },
    ];
  }
  return [
    { key: 'kimi2.5', value: 'kimi-k2.5' },
    { key: 'glm5', value: 'glm-5' },
  ];
}

function createChannelFormModal({ title = '新增渠道', initial = null, onSubmit }) {
  let mode = 'visual';
  let pairs = modelsToPairs(initial?.models || {});
  if (pairs.length === 0) pairs = [{ key: '', value: '' }];

  const initialProviderType = initial?.provider_type || 'openai_compatible';
  const providerMatched = PROVIDER_OPTIONS.some((x) => x.value === initialProviderType);

  const modal = h('div', { className: 'modal-overlay' },
    h('div', { className: 'modal-card', style: { width: '860px', maxWidth: '96vw' } },
      h('div', { className: 'modal-header' },
        h('span', { className: 'modal-icon' }, icon('channels', 24)),
        h('h3', { className: 'modal-title' }, title),
      ),
      h('div', { className: 'modal-body' },
        h('label', { className: 'input-label' }, '渠道 ID（可留空自动生成）'),
        h('input', {
          id: 'ch-id',
          className: 'input-field',
          value: initial?.id || '',
          disabled: !!initial,
          placeholder: '留空自动生成，例如：openai_compatible_2',
        }),

        h('label', { className: 'input-label mt-md' }, '显示名称'),
        h('input', {
          id: 'ch-name',
          className: 'input-field',
          value: initial?.display_name || '',
          placeholder: 'Infini Coding',
        }),

        h('label', { className: 'input-label mt-md' }, '渠道 URL / API Base'),
        h('input', {
          id: 'ch-api-base',
          className: 'input-field',
          value: initial?.api_base || '',
          placeholder: '支持粘贴完整地址，如 https://cloud.infini-ai.com/maas/coding/v1/chat/completions',
        }),

        h('label', { className: 'input-label mt-md' }, 'Provider Type'),
        h('select', {
          id: 'ch-provider-type-select',
          className: 'select-field',
        }, ...PROVIDER_OPTIONS.map((opt) =>
          h('option', {
            value: opt.value,
            selected: providerMatched ? initialProviderType === opt.value : opt.value === '__custom__',
          }, opt.label)
        )),

        h('div', { id: 'provider-custom-wrap', className: 'mt-sm', style: `display:${providerMatched ? 'none' : 'block'}` },
          h('input', {
            id: 'ch-provider-type-custom',
            className: 'input-field',
            value: providerMatched ? '' : initialProviderType,
            placeholder: '自定义 provider_type（例如 infini_custom）',
          })
        ),

        h('div', { className: 'mt-md', style: 'border:1px solid rgba(70,72,79,.25); border-radius:12px; padding:12px;' },
          h('div', { className: 'flex items-center justify-between mb-sm' },
            h('div', { className: 'font-headline' }, '模型重定向'),
            h('button', {
              className: 'btn btn-ghost btn-sm',
              type: 'button',
              onClick: () => {
                const apiBase = document.getElementById('ch-api-base').value;
                pairs = inferTemplateByUrl(apiBase);
                renderPairs();
              },
            }, '填入模板')
          ),
          h('div', { className: 'mb-sm' },
            h('button', {
              id: 'mode-visual', className: 'btn btn-ghost btn-sm', type: 'button',
              onClick: () => { mode = 'visual'; syncTabs(); }
            }, '可视化'),
            h('span', { className: 'text-muted', style: 'margin:0 8px' }, '/'),
            h('button', {
              id: 'mode-raw', className: 'btn btn-ghost btn-sm', type: 'button',
              onClick: () => { mode = 'raw'; syncTabs(); }
            }, '手动编辑')
          ),

          h('div', { id: 'models-visual-wrap' },
            h('div', { id: 'models-pairs' }),
            h('button', {
              className: 'btn btn-ghost btn-sm mt-sm',
              type: 'button',
              onClick: () => {
                pairs.push({ key: '', value: '' });
                renderPairs();
              }
            }, '+ 添加键值对'),
            h('div', { className: 'text-muted mt-sm' }, '键为请求中的模型名，值为要替换的模型名')
          ),

          h('div', { id: 'models-raw-wrap', style: 'display:none' },
            h('textarea', {
              id: 'ch-models-raw',
              className: 'input-field',
              style: { minHeight: '160px', fontFamily: 'JetBrains Mono, monospace' },
            }, JSON.stringify(pairsToModels(pairs), null, 2))
          )
        ),

        h('label', { className: 'input-checkbox-label mt-md' },
          h('input', {
            id: 'ch-enabled',
            type: 'checkbox',
            checked: initial?.enabled ?? true,
          }),
          h('span', {}, ' 启用渠道')
        ),
        h('div', { id: 'ch-form-error', className: 'auth-error-msg', style: 'display:none' })
      ),
      h('div', { className: 'modal-footer' },
        h('button', { className: 'btn btn-ghost', onClick: () => modal.remove() }, '取消'),
        h('button', {
          className: 'btn btn-primary',
          onClick: async () => {
            try {
              const selectVal = document.getElementById('ch-provider-type-select').value;
              const providerType = selectVal === '__custom__'
                ? (document.getElementById('ch-provider-type-custom').value || '').trim()
                : selectVal;
              if (!providerType) throw new Error('请填写 provider_type');

              let models;
              if (mode === 'visual') {
                models = pairsToModels(pairs);
              } else {
                const raw = document.getElementById('ch-models-raw').value;
                models = raw.trim() ? JSON.parse(raw) : {};
              }

              const payload = {
                id: (document.getElementById('ch-id').value || '').trim() || null,
                display_name: (document.getElementById('ch-name').value || '').trim() || null,
                api_base: (document.getElementById('ch-api-base').value || '').trim(),
                provider_type: providerType,
                enabled: document.getElementById('ch-enabled').checked,
                models,
                api_keys: initial?.api_keys || [],
                settings: initial?.settings || { rotation_mode: 'balanced', max_concurrent_requests_per_key: 1, ignore_models: [], whitelist_models: [] },
              };
              await onSubmit(payload);
              modal.remove();
            } catch (e) {
              const err = document.getElementById('ch-form-error');
              err.style.display = 'block';
              err.textContent = e.message;
            }
          },
        }, '保存')
      )
    )
  );

  function renderPairs() {
    const box = modal.querySelector('#models-pairs');
    box.innerHTML = '';
    pairs.forEach((p, idx) => {
      box.appendChild(h('div', { className: 'flex items-center gap-sm mb-sm' },
        h('input', {
          className: 'input-field',
          style: { flex: '1' },
          value: p.key,
          placeholder: '请求模型名（key）',
          onInput: (e) => { p.key = e.target.value; }
        }),
        h('input', {
          className: 'input-field',
          style: { flex: '1' },
          value: p.value,
          placeholder: '目标模型名（value）',
          onInput: (e) => { p.value = e.target.value; }
        }),
        h('button', {
          className: 'btn btn-ghost btn-sm',
          type: 'button',
          onClick: () => {
            pairs.splice(idx, 1);
            if (pairs.length === 0) pairs.push({ key: '', value: '' });
            renderPairs();
          }
        }, '删除')
      ));
    });
  }

  function syncTabs() {
    const v = modal.querySelector('#models-visual-wrap');
    const r = modal.querySelector('#models-raw-wrap');
    if (mode === 'visual') {
      const raw = modal.querySelector('#ch-models-raw').value;
      try {
        pairs = modelsToPairs(JSON.parse(raw || '{}'));
        if (pairs.length === 0) pairs = [{ key: '', value: '' }];
      } catch (_) {
        // keep current pairs if JSON invalid
      }
      renderPairs();
      v.style.display = '';
      r.style.display = 'none';
    } else {
      modal.querySelector('#ch-models-raw').value = JSON.stringify(pairsToModels(pairs), null, 2);
      v.style.display = 'none';
      r.style.display = '';
    }
  }

  modal.querySelector('#ch-provider-type-select').addEventListener('change', (e) => {
    modal.querySelector('#provider-custom-wrap').style.display = e.target.value === '__custom__' ? 'block' : 'none';
  });

  renderPairs();
  syncTabs();
  return modal;
}

function createKeyModal({ channelId, onSubmit }) {
  const modal = h('div', { className: 'modal-overlay' },
    h('div', { className: 'modal-card', style: { width: '520px', maxWidth: '95vw' } },
      h('div', { className: 'modal-header' },
        h('span', { className: 'modal-icon' }, icon('key', 24)),
        h('h3', { className: 'modal-title' }, `新增 Key - ${channelId}`),
      ),
      h('div', { className: 'modal-body' },
        h('label', { className: 'input-label' }, 'Key ID'),
        h('input', { id: 'key-id', className: 'input-field', placeholder: 'key_1' }),
        h('label', { className: 'input-label mt-md' }, 'Key Value'),
        h('input', { id: 'key-val', className: 'input-field', placeholder: 'sk-xxx' }),
        h('label', { className: 'input-checkbox-label mt-md' },
          h('input', { id: 'key-enabled', type: 'checkbox', checked: true }),
          h('span', {}, ' 启用')
        ),
        h('div', { id: 'key-form-error', className: 'auth-error-msg', style: 'display:none' })
      ),
      h('div', { className: 'modal-footer' },
        h('button', { className: 'btn btn-ghost', onClick: () => modal.remove() }, '取消'),
        h('button', {
          className: 'btn btn-primary',
          onClick: async () => {
            try {
              await onSubmit({
                id: document.getElementById('key-id').value.trim(),
                value: document.getElementById('key-val').value.trim(),
                enabled: document.getElementById('key-enabled').checked,
              });
              modal.remove();
            } catch (e) {
              const err = document.getElementById('key-form-error');
              err.style.display = 'block';
              err.textContent = e.message;
            }
          }
        }, '保存')
      )
    )
  );
  return modal;
}

export async function renderChannels(container) {
  clearChildren(container);
  container.appendChild(h('div', { className: 'page-loading' }, '加载中...'));

  try {
    const [quotaStats, adminResp] = await Promise.all([
      api.getQuotaStats().catch(() => ({ providers: {} })),
      api.getChannels(),
    ]);
    clearChildren(container);

    const providers = quotaStats.providers || {};
    const adminChannels = adminResp.channels || [];

    const page = h('div', { className: 'page', id: 'page-channels' });

    page.appendChild(h('div', { className: 'page-title' },
      h('span', { className: 'page-title-icon' }, icon('link', 24)),
      '渠道管理',
      h('div', { className: 'page-actions' },
        h('button', {
          className: 'btn btn-primary btn-sm',
          onClick: () => {
            const modal = createChannelFormModal({
              title: '新增渠道',
              onSubmit: async (payload) => {
                const res = await api.createChannel(payload);
                const createdId = res?.config?.created_channel_id || res?.created_channel_id;
                showToast(createdId ? `渠道创建成功: ${createdId}` : '渠道创建成功', 'success');
                renderChannels(container);
              }
            });
            document.body.appendChild(modal);
          }
        }, icon('check', 14), ' 新增渠道'),
        h('button', {
          className: 'btn btn-ghost btn-sm',
          onClick: async () => {
            await api.applyAdminConfig();
            showToast('配置已应用并触发重载', 'success');
          }
        }, icon('refresh', 14), ' 应用配置')
      )
    ));

    const channelList = h('div', { className: 'channel-list' });

    adminChannels.forEach((ch, index) => {
      const provData = providers[ch.id] || {};
      const totalTokens = ((provData.tokens || {}).total_input || 0) + ((provData.tokens || {}).total_output || 0);

      const accordion = h('div', { className: `channel-accordion ${index === 0 ? 'channel-accordion-open' : ''}` },
        h('div', {
          className: 'channel-accordion-header',
          onClick: (e) => e.currentTarget.parentElement.classList.toggle('channel-accordion-open')
        },
          h('div', { className: 'channel-accordion-left' },
            h('span', { className: 'channel-accordion-arrow' }, '▶'),
            h('span', { className: 'channel-accordion-name font-headline' }, ch.display_name || ch.id),
            h('div', { className: 'channel-accordion-badges' },
              h('span', { className: 'badge badge-sm badge-outline' }, `${(ch.api_keys || []).length} Keys`),
              h('span', { className: 'badge badge-sm badge-outline' }, ch.provider_type || 'openai_compatible'),
              h('span', { className: `badge badge-sm ${ch.enabled ? 'badge-success' : 'badge-error'}` }, ch.enabled ? '启用' : '停用')
            )
          ),
          h('div', { className: 'channel-accordion-right text-muted' },
            h('span', {}, `请求: ${formatNumber(provData.total_requests || 0)}`),
            h('span', {}, `Token: ${formatTokens(totalTokens)}`)
          )
        ),

        h('div', { className: 'channel-accordion-body' },
          h('div', { className: 'flex gap-sm mb-md' },
            h('button', {
              className: 'btn btn-ghost btn-sm',
              onClick: () => {
                const modal = createChannelFormModal({
                  title: `编辑渠道 - ${ch.id}`,
                  initial: ch,
                  onSubmit: async (payload) => {
                    await api.updateChannel(ch.id, {
                      display_name: payload.display_name,
                      enabled: payload.enabled,
                      api_base: payload.api_base,
                      provider_type: payload.provider_type,
                      models: payload.models,
                      settings: payload.settings,
                    });
                    showToast('渠道已更新', 'success');
                    renderChannels(container);
                  }
                });
                document.body.appendChild(modal);
              }
            }, '编辑渠道'),
            h('button', {
              className: 'btn btn-ghost btn-sm',
              onClick: async () => {
                const ok = confirm(`确认删除渠道 ${ch.id}？`);
                if (!ok) return;
                await api.deleteChannel(ch.id);
                showToast('渠道已删除', 'success');
                renderChannels(container);
              }
            }, '删除渠道'),
            h('button', {
              className: 'btn btn-ghost btn-sm',
              onClick: () => {
                const modal = createKeyModal({
                  channelId: ch.id,
                  onSubmit: async (payload) => {
                    await api.addChannelKey(ch.id, payload);
                    showToast('Key 已添加', 'success');
                    renderChannels(container);
                  }
                });
                document.body.appendChild(modal);
              }
            }, '新增 Key'),
            h('button', {
              className: 'btn btn-ghost btn-sm',
              onClick: async () => {
                const result = await api.testChannel(ch.id);
                showToast(result.message || '测试完成', result.ok ? 'success' : 'warning');
              }
            }, '测试渠道')
          ),

          KeyTable({
            credentials: (ch.api_keys || []).map(k => ({
              credential: `${k.id}:${k.value}`,
              status: k.enabled ? 'active' : 'exhausted',
              requests: 0,
              tokens: {},
              approx_cost: 0,
              cooldown_until: null,
            })),
            onForceRefresh: async () => {
              await api.refreshQuota('force_refresh', 'provider', ch.id);
              showToast('配额刷新完成', 'success');
              renderChannels(container);
            }
          }),

          (ch.api_keys || []).length > 0
            ? h('div', { className: 'mt-md' },
              h('div', { className: 'text-muted mb-sm' }, 'Key 管理'),
              ...ch.api_keys.map(k =>
                h('div', { className: 'flex items-center gap-sm mb-sm' },
                  h('code', { className: 'text-mono' }, `${k.id} (${k.enabled ? '启用' : '停用'})`),
                  h('button', {
                    className: 'btn btn-ghost btn-sm',
                    onClick: async () => {
                      await api.updateChannelKey(ch.id, k.id, { enabled: !k.enabled });
                      showToast('Key 状态已更新', 'success');
                      renderChannels(container);
                    }
                  }, k.enabled ? '停用' : '启用'),
                  h('button', {
                    className: 'btn btn-ghost btn-sm',
                    onClick: async () => {
                      const ok = confirm(`确认删除 key ${k.id}？`);
                      if (!ok) return;
                      await api.deleteChannelKey(ch.id, k.id);
                      showToast('Key 已删除', 'success');
                      renderChannels(container);
                    }
                  }, '删除')
                )
              )
            )
            : null
        )
      );

      channelList.appendChild(accordion);
    });

    if (adminChannels.length === 0) {
      channelList.appendChild(h('div', { className: 'page-empty' }, '未发现可管理渠道，点击“新增渠道”开始配置'));
    }

    page.appendChild(channelList);
    container.appendChild(page);

  } catch (err) {
    clearChildren(container);
    container.appendChild(h('div', { className: 'page-error' },
      h('h3', {}, '加载失败'),
      h('p', { className: 'text-muted' }, err.message),
      h('button', { className: 'btn btn-primary mt-lg', onClick: () => renderChannels(container) }, '重试')
    ));
  }
}
