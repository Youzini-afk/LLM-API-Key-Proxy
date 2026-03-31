// ============================================================
// Models Page — 模型与虚拟路由管理
// ============================================================
import { h, clearChildren, icon } from '../utils/dom.js';
import { api } from '../api.js';
import { RouteChain } from '../components/ui.js';
import { showToast } from '../components/toast.js';

function vmModal({ title = '新增虚拟模型', initialName = '', initialConfig = null, onSubmit, lockName = false }) {
  const cfg = initialConfig || {
    enabled: true,
    strategy: 'sequential',
    targets: [{ model: '', enabled: true, weight: 100 }],
  };

  const renderTargets = (container) => {
    container.innerHTML = '';
    cfg.targets.forEach((t, idx) => {
      const row = h('div', { className: 'flex gap-sm items-center mb-sm' },
        h('input', {
          className: 'input-field',
          style: { flex: '1' },
          value: t.model,
          placeholder: 'provider/model',
          onInput: (e) => { t.model = e.target.value; }
        }),
        h('input', {
          type: 'number',
          className: 'input-field',
          style: { width: '96px' },
          value: String(t.weight || 100),
          onInput: (e) => { t.weight = parseInt(e.target.value || '100', 10); }
        }),
        h('label', { className: 'input-checkbox-label' },
          h('input', {
            type: 'checkbox',
            checked: t.enabled,
            onChange: (e) => { t.enabled = e.target.checked; }
          }),
          h('span', {}, '启用')
        ),
        h('button', {
          className: 'btn btn-ghost btn-sm',
          onClick: () => {
            cfg.targets.splice(idx, 1);
            renderTargets(container);
          }
        }, '删除')
      );
      container.appendChild(row);
    });
  };

  const modal = h('div', { className: 'modal-overlay' },
    h('div', { className: 'modal-card', style: { width: '780px', maxWidth: '96vw' } },
      h('div', { className: 'modal-header' },
        h('span', { className: 'modal-icon' }, icon('route', 24)),
        h('h3', { className: 'modal-title' }, title)
      ),
      h('div', { className: 'modal-body' },
        h('label', { className: 'input-label' }, '逻辑模型名'),
        h('input', {
          id: 'vm-name',
          className: 'input-field',
          value: initialName,
          disabled: lockName,
          placeholder: 'kimi2.5'
        }),
        h('label', { className: 'input-label mt-md' }, '策略'),
        h('select', {
          id: 'vm-strategy',
          className: 'select-field',
          onChange: (e) => { cfg.strategy = e.target.value; }
        },
          h('option', { value: 'sequential', selected: cfg.strategy === 'sequential' }, 'sequential'),
          h('option', { value: 'primary_backup', selected: cfg.strategy === 'primary_backup' }, 'primary_backup'),
          h('option', { value: 'weighted_random', selected: cfg.strategy === 'weighted_random' }, 'weighted_random')
        ),
        h('label', { className: 'input-checkbox-label mt-md' },
          h('input', {
            id: 'vm-enabled',
            type: 'checkbox',
            checked: cfg.enabled,
            onChange: (e) => { cfg.enabled = e.target.checked; }
          }),
          h('span', {}, ' 启用虚拟模型')
        ),
        h('div', { className: 'mt-md mb-sm font-headline' }, 'Targets'),
        h('div', { id: 'vm-targets' }),
        h('button', {
          className: 'btn btn-ghost btn-sm mt-sm',
          onClick: () => {
            cfg.targets.push({ model: '', enabled: true, weight: 100 });
            renderTargets(document.getElementById('vm-targets'));
          }
        }, '新增 Target'),
        h('div', { id: 'vm-form-error', className: 'auth-error-msg', style: 'display:none' })
      ),
      h('div', { className: 'modal-footer' },
        h('button', { className: 'btn btn-ghost', onClick: () => modal.remove() }, '取消'),
        h('button', {
          className: 'btn btn-primary',
          onClick: async () => {
            try {
              const name = document.getElementById('vm-name').value.trim();
              if (!name) throw new Error('模型名不能为空');
              const finalConfig = {
                enabled: cfg.enabled,
                strategy: cfg.strategy,
                targets: cfg.targets,
              };
              await onSubmit(name, finalConfig);
              modal.remove();
            } catch (e) {
              const err = document.getElementById('vm-form-error');
              err.style.display = 'block';
              err.textContent = e.message;
            }
          }
        }, '保存')
      )
    )
  );

  setTimeout(() => {
    const targetEl = modal.querySelector('#vm-targets');
    renderTargets(targetEl);
  }, 0);

  return modal;
}

export async function renderModels(container) {
  clearChildren(container);
  container.appendChild(h('div', { className: 'page-loading' }, '加载中...'));

  try {
    const [modelsResp, vmResp] = await Promise.all([
      api.getModels(true),
      api.getVirtualModels(),
    ]);

    clearChildren(container);
    const page = h('div', { className: 'page', id: 'page-models' });
    const allModels = modelsResp.data || [];
    const virtualModelsMap = vmResp.virtual_models || {};
    const virtualModels = Object.entries(virtualModelsMap).map(([name, cfg]) => ({ name, ...cfg }));

    let searchQuery = '';
    let virtualOnly = false;

    page.appendChild(h('div', { className: 'page-title' },
      h('span', { className: 'page-title-icon' }, icon('robot', 24)),
      '模型与路由管理',
      h('div', { className: 'page-actions' },
        h('input', {
          type: 'text',
          className: 'input-field input-sm',
          placeholder: '搜索模型...',
          id: 'model-search',
          onInput: (e) => { searchQuery = e.target.value.toLowerCase(); renderList(); }
        }),
        h('label', { className: 'input-checkbox-label' },
          h('input', {
            type: 'checkbox',
            id: 'virtual-only-toggle',
            onChange: (e) => { virtualOnly = e.target.checked; renderList(); }
          }),
          h('span', {}, ' 仅虚拟模型')
        ),
        h('button', {
          className: 'btn btn-primary btn-sm',
          onClick: () => {
            const modal = vmModal({
              title: '新增虚拟模型',
              onSubmit: async (name, cfg) => {
                await api.createVirtualModel({ name, config: cfg });
                showToast('虚拟模型已创建', 'success');
                renderModels(container);
              }
            });
            document.body.appendChild(modal);
          }
        }, icon('check', 14), ' 新增虚拟模型')
      )
    ));

    const virtualSection = h('div', { className: 'section', id: 'virtual-models-section' });
    virtualSection.appendChild(h('div', { className: 'section-title' },
      h('span', { className: 'section-title-icon' }, icon('route', 20)),
      '虚拟模型 (可编辑)'
    ));

    const virtualContainer = h('div', { className: 'card-grid-2', id: 'virtual-models-grid' });
    virtualSection.appendChild(virtualContainer);

    const providerSection = h('div', { className: 'section', id: 'provider-models-section' });
    providerSection.appendChild(h('div', { className: 'section-title' },
      h('span', { className: 'section-title-icon' }, icon('list', 20)),
      '全部模型',
      h('span', { className: 'section-subtitle', id: 'model-count' })
    ));

    const tableContainer = h('div', { id: 'models-table-container' });
    providerSection.appendChild(tableContainer);

    page.appendChild(virtualSection);
    page.appendChild(providerSection);

    function renderList() {
      clearChildren(virtualContainer);
      clearChildren(tableContainer);

      const filteredVirtual = virtualModels.filter(vm =>
        !searchQuery || vm.name.toLowerCase().includes(searchQuery)
      );

      if (filteredVirtual.length > 0) {
        filteredVirtual.forEach(vm => {
          const cardWrap = h('div', { className: 'card' },
            h('div', { className: 'card-body' },
              RouteChain(vm),
              h('div', { className: 'flex gap-sm mt-md' },
                h('button', {
                  className: 'btn btn-ghost btn-sm',
                  onClick: () => {
                    const modal = vmModal({
                      title: `编辑虚拟模型 - ${vm.name}`,
                      initialName: vm.name,
                      lockName: true,
                      initialConfig: {
                        enabled: vm.enabled,
                        strategy: vm.strategy,
                        targets: vm.targets || [],
                      },
                      onSubmit: async (_name, cfg) => {
                        await api.updateVirtualModel(vm.name, cfg);
                        showToast('虚拟模型已更新', 'success');
                        renderModels(container);
                      }
                    });
                    document.body.appendChild(modal);
                  }
                }, '编辑'),
                h('button', {
                  className: 'btn btn-ghost btn-sm',
                  onClick: async () => {
                    const ok = confirm(`确认删除虚拟模型 ${vm.name}？`);
                    if (!ok) return;
                    await api.deleteVirtualModel(vm.name);
                    showToast('虚拟模型已删除', 'success');
                    renderModels(container);
                  }
                }, '删除')
              )
            )
          );
          virtualContainer.appendChild(cardWrap);
        });
      } else {
        virtualContainer.appendChild(h('div', { className: 'text-muted' }, '未配置虚拟模型'));
      }

      if (virtualOnly) {
        providerSection.style.display = 'none';
        return;
      }
      providerSection.style.display = '';

      const filtered = allModels.filter(m =>
        !searchQuery || m.id.toLowerCase().includes(searchQuery)
      );

      const countEl = document.getElementById('model-count');
      if (countEl) countEl.textContent = `共 ${filtered.length} 个模型`;

      const table = h('table', { className: 'key-table' },
        h('thead', {},
          h('tr', {},
            h('th', {}, '模型 ID'),
            h('th', {}, 'Provider'),
            h('th', {}, '上下文窗口'),
          )
        ),
        h('tbody', {},
          ...filtered.slice(0, 100).map(model => {
            const parts = model.id.split('/');
            const provider = parts.length > 1 ? parts[0] : (model.owned_by || '-');
            const ctxWindow = model.context_window ? `${(model.context_window / 1000).toFixed(0)}K` : '-';
            return h('tr', {},
              h('td', { className: 'text-mono' }, model.id),
              h('td', {}, provider),
              h('td', {}, ctxWindow),
            );
          })
        )
      );

      tableContainer.appendChild(table);
      if (filtered.length > 100) {
        tableContainer.appendChild(h('div', { className: 'text-muted mt-md' }, `显示前 100 个，共 ${filtered.length} 个模型`));
      }
    }

    renderList();
    container.appendChild(page);

  } catch (err) {
    clearChildren(container);
    container.appendChild(h('div', { className: 'page-error' },
      h('h3', {}, '加载失败'),
      h('p', { className: 'text-muted' }, err.message),
      h('button', { className: 'btn btn-primary mt-lg', onClick: () => renderModels(container) }, '重试')
    ));
  }
}
