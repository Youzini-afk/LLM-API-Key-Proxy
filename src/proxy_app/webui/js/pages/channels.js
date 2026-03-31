// ============================================================
// Channels Page — 渠道管理（可读 + 可管）
// ============================================================
import { h, clearChildren, icon, delegate } from '../utils/dom.js';
import { api } from '../api.js';
import { formatNumber, formatTokens } from '../utils/format.js';
import { KeyTable } from '../components/ui.js';
import { showToast } from '../components/toast.js';

function parseModelsText(value) {
  if (!value || !value.trim()) return {};
  return JSON.parse(value);
}

function createChannelFormModal({ title = '新增渠道', initial = null, onSubmit }) {
  const modal = h('div', { className: 'modal-overlay' },
    h('div', { className: 'modal-card', style: { width: '640px', maxWidth: '95vw' } },
      h('div', { className: 'modal-header' },
        h('span', { className: 'modal-icon' }, icon('channels', 24)),
        h('h3', { className: 'modal-title' }, title),
      ),
      h('div', { className: 'modal-body' },
        h('label', { className: 'input-label' }, '渠道 ID (小写+下划线)'),
        h('input', {
          id: 'ch-id',
          className: 'input-field',
          value: initial?.id || '',
          disabled: !!initial,
          placeholder: 'dashscope_a',
        }),
        h('label', { className: 'input-label mt-md' }, '显示名称'),
        h('input', {
          id: 'ch-name',
          className: 'input-field',
          value: initial?.display_name || '',
          placeholder: 'DashScope A',
        }),
        h('label', { className: 'input-label mt-md' }, 'API Base'),
        h('input', {
          id: 'ch-api-base',
          className: 'input-field',
          value: initial?.api_base || '',
          placeholder: 'https://xxx/v1',
        }),
        h('label', { className: 'input-label mt-md' }, 'Provider Type'),
        h('input', {
          id: 'ch-provider-type',
          className: 'input-field',
          value: initial?.provider_type || 'openai_compatible',
          placeholder: 'openai_compatible',
        }),
        h('label', { className: 'input-label mt-md' }, '模型映射 JSON'),
        h('textarea', {
          id: 'ch-models',
          className: 'input-field',
          style: { minHeight: '120px', fontFamily: 'JetBrains Mono, monospace' },
        }, JSON.stringify(initial?.models || {}, null, 2)),
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
        h('button', {
          className: 'btn btn-ghost',
          onClick: () => modal.remove(),
        }, '取消'),
        h('button', {
          className: 'btn btn-primary',
          onClick: async () => {
            try {
              const payload = {
                id: document.getElementById('ch-id').value.trim(),
                display_name: document.getElementById('ch-name').value.trim() || null,
                api_base: document.getElementById('ch-api-base').value.trim(),
                provider_type: document.getElementById('ch-provider-type').value.trim() || 'openai_compatible',
                enabled: document.getElementById('ch-enabled').checked,
                models: parseModelsText(document.getElementById('ch-models').value),
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
                await api.createChannel(payload);
                showToast('渠道创建成功', 'success');
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
      const creds = provData.credentials || [];
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
