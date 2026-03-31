// ============================================================
// Models Page — 模型列表
// ============================================================
import { h, clearChildren } from '../utils/dom.js';
import { api } from '../api.js';
import { formatCost, getStrategyLabel } from '../utils/format.js';
import { RouteChain } from '../components/ui.js';
import { showToast } from '../components/toast.js';

export async function renderModels(container) {
  clearChildren(container);
  container.appendChild(h('div', { className: 'page-loading' }, '加载中...'));

  try {
    const [modelsResp, quotaStats] = await Promise.all([
      api.getModels(true),
      api.getQuotaStats(),
    ]);

    clearChildren(container);
    const page = h('div', { className: 'page', id: 'page-models' });
    const allModels = modelsResp.data || [];

    // State
    let searchQuery = '';
    let virtualOnly = false;

    // Page header with search
    page.appendChild(h('div', { className: 'page-title' },
      h('span', { className: 'page-title-icon' }, '🤖'),
      '模型列表',
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
        )
      )
    ));

    // --- Virtual Models Section ---
    const virtualSection = h('div', { className: 'section', id: 'virtual-models-section' });
    virtualSection.appendChild(h('div', { className: 'section-title' },
      h('span', { className: 'section-title-icon' }, '🔀'),
      '虚拟模型 (聚合路由)'
    ));

    const virtualContainer = h('div', { className: 'card-grid-2', id: 'virtual-models-grid' });
    virtualSection.appendChild(virtualContainer);

    // --- Provider Models Section ---
    const providerSection = h('div', { className: 'section', id: 'provider-models-section' });
    providerSection.appendChild(h('div', { className: 'section-title' },
      h('span', { className: 'section-title-icon' }, '📋'),
      '全部模型',
      h('span', { className: 'section-subtitle', id: 'model-count' })
    ));

    const tableContainer = h('div', { id: 'models-table-container' });
    providerSection.appendChild(tableContainer);

    page.appendChild(virtualSection);
    page.appendChild(providerSection);

    // Build virtual model data from cross-provider analysis
    const providers = quotaStats.providers || {};
    const modelProviderMap = {};
    for (const [provName, provData] of Object.entries(providers)) {
      for (const cred of (provData.credentials || [])) {
        if (!cred.models) continue;
        for (const modelName of Object.keys(cred.models)) {
          const shortName = modelName.split('/').pop();
          if (!modelProviderMap[shortName]) modelProviderMap[shortName] = new Set();
          modelProviderMap[shortName].add(provName);
        }
      }
    }

    const virtualModels = Object.entries(modelProviderMap)
      .filter(([_, pSet]) => pSet.size > 1)
      .map(([name, pSet]) => ({
        name,
        strategy: 'sequential',
        targets: [...pSet].map(p => ({ model: `${p}/${name}`, enabled: true, weight: 100 })),
      }));

    // Render function (called on search/filter change)
    function renderList() {
      clearChildren(virtualContainer);
      clearChildren(tableContainer);

      // Virtual models
      const filteredVirtual = virtualModels.filter(vm =>
        !searchQuery || vm.name.toLowerCase().includes(searchQuery)
      );

      if (filteredVirtual.length > 0) {
        filteredVirtual.forEach(vm => {
          virtualContainer.appendChild(RouteChain(vm));
        });
        virtualSection.style.display = '';
      } else {
        virtualSection.style.display = virtualOnly ? '' : '';
        if (virtualModels.length === 0) {
          virtualContainer.appendChild(h('div', { className: 'text-muted' }, '未配置虚拟模型'));
        }
      }

      if (virtualOnly) {
        providerSection.style.display = 'none';
        return;
      }
      providerSection.style.display = '';

      // Provider models table
      const filtered = allModels.filter(m =>
        !searchQuery || m.id.toLowerCase().includes(searchQuery)
      );

      const countEl = document.getElementById('model-count');
      if (countEl) countEl.textContent = `共 ${filtered.length} 个模型`;

      const capabilities = (model) => {
        const caps = [];
        if (model.supported_modalities?.includes('text')) caps.push({ label: '文本', class: 'badge-primary' });
        if (model.supported_modalities?.includes('image')) caps.push({ label: '视觉', class: 'badge-success' });
        if (model.capabilities?.tool_choice || model.capabilities?.function_calling) caps.push({ label: '工具', class: 'badge-warning' });
        if (model.capabilities?.reasoning) caps.push({ label: '推理', class: 'badge-info' });
        return caps;
      };

      const table = h('table', { className: 'key-table' },
        h('thead', {},
          h('tr', {},
            h('th', {}, '模型 ID'),
            h('th', {}, 'Provider'),
            h('th', {}, '定价 (输入/输出)'),
            h('th', {}, '上下文窗口'),
            h('th', {}, '能力'),
          )
        ),
        h('tbody', {},
          ...filtered.slice(0, 100).map(model => {
            const parts = model.id.split('/');
            const provider = parts.length > 1 ? parts[0] : (model.owned_by || '-');
            const inputCost = model.input_cost_per_token ? `$${(model.input_cost_per_token * 1e6).toFixed(2)}` : '-';
            const outputCost = model.output_cost_per_token ? `$${(model.output_cost_per_token * 1e6).toFixed(2)}` : '-';
            const ctxWindow = model.context_window ? `${(model.context_window / 1000).toFixed(0)}K` : '-';
            const caps = capabilities(model);

            return h('tr', {},
              h('td', { className: 'text-mono' }, model.id),
              h('td', {}, provider),
              h('td', {}, inputCost !== '-' ? `${inputCost} / ${outputCost}` : '-'),
              h('td', {}, ctxWindow),
              h('td', {},
                ...caps.map(c => h('span', { className: `badge badge-sm ${c.class}` }, c.label))
              )
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
