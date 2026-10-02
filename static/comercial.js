(() => {
    const form = document.querySelector('#search-form');
    const searchButton = document.querySelector('#search-button');
    const searchError = document.querySelector('#search-error');
    const resultsStatus = document.querySelector('#results-status');
    const resultsWrap = document.querySelector('#results-wrap');
    const resultsBody = document.querySelector('#results-body');
    const resultCount = document.querySelector('#result-count');
    const pagination = document.querySelector('#pagination');
    const previousButton = document.querySelector('#previous-page');
    const nextButton = document.querySelector('#next-page');
    const pageLabel = document.querySelector('#page-label');
    const pageJumpForm = document.querySelector('#page-jump-form');
    const pageJumpInput = document.querySelector('#page-jump-input');
    const totalPagesLabel = document.querySelector('#total-pages-label');
    const cnaeInput = document.querySelector('#cnaes');
    const cnaeLookupInput = document.querySelector('#cnae-lookup-input');
    const cnaeLookupButton = document.querySelector('#cnae-lookup-button');
    const cnaeLookupStatus = document.querySelector('#cnae-lookup-status');
    const cnaeSuggestions = document.querySelector('#cnae-suggestions');
    const dialog = document.querySelector('#company-dialog');
    const dialogTitle = document.querySelector('#dialog-title');
    const companyDetails = document.querySelector('#company-details');

    let page = 1;
    let totalPages = 0;
    let searchController;
    let cnaeController;

    function formatCnpj(value) {
        const digits = value.replace(/\D/g, '');
        if (digits.length !== 14) return value;
        return digits.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
    }

    function formatDate(value) {
        if (!value) return 'Não informado';
        const date = new Date(`${value}T00:00:00`);
        return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('pt-BR').format(date);
    }

    function phoneText(phones) {
        return (phones || [])
            .filter((phone) => !phone.is_fax && phone.numero)
            .map((phone) => `(${phone.ddd}) ${phone.numero}`)
            .join(' / ') || 'Não informado';
    }

    function appendTextCell(row, value, className = '') {
        const cell = document.createElement('td');
        if (className) cell.className = className;
        cell.textContent = value || 'Não informado';
        row.append(cell);
        return cell;
    }

    function renderCompanies(companies) {
        resultsBody.replaceChildren();
        for (const company of companies) {
            const row = document.createElement('tr');
            appendTextCell(row, formatCnpj(company.cnpj), 'cnpj-cell');

            const companyCell = document.createElement('td');
            const legalName = document.createElement('span');
            legalName.className = 'company-name';
            legalName.textContent = company.razao_social || 'Razão social não informada';
            companyCell.append(legalName);
            if (company.nome_fantasia) {
                const fantasyName = document.createElement('span');
                fantasyName.className = 'company-fantasy';
                fantasyName.textContent = company.nome_fantasia;
                companyCell.append(fantasyName);
            }
            row.append(companyCell);

            const statusCell = document.createElement('td');
            const status = document.createElement('span');
            status.className = 'status-label';
            status.dataset.status = company.situacao_cadastral || '';
            status.textContent = company.situacao_cadastral || 'Não informada';
            statusCell.append(status);
            row.append(statusCell);

            appendTextCell(row, company.cnae_principal, 'cnae-cell');
            appendTextCell(row, [company.municipio, company.uf].filter(Boolean).join(' / '));
            appendTextCell(row, phoneText(company.telefones));

            const actionCell = document.createElement('td');
            const detailsButton = document.createElement('button');
            detailsButton.type = 'button';
            detailsButton.className = 'detail-button';
            detailsButton.textContent = 'Detalhes';
            detailsButton.addEventListener('click', () => openCompanyDetails(company.cnpj));
            actionCell.append(detailsButton);
            row.append(actionCell);
            resultsBody.append(row);
        }
    }

    function setLoading(isLoading) {
        searchButton.disabled = isLoading;
        searchButton.querySelector('span').textContent = isLoading ? 'Pesquisando...' : 'Pesquisar empresas';
        resultsStatus.hidden = false;
        resultsWrap.hidden = true;
        pagination.hidden = true;
        if (isLoading) {
            resultsStatus.dataset.kind = 'loading';
            resultsStatus.textContent = 'Consultando a fonte de dados...';
            resultCount.textContent = 'Carregando';
        }
    }

    function buildSearchUrl(targetPage) {
        const params = new URLSearchParams();
        const formData = new FormData(form);
        const codes = String(formData.get('cnaes') || '')
            .split(/[,;\n]+/)
            .map((code) => code.trim())
            .filter(Boolean);

        for (const code of codes) params.append('cnaes', code);
        for (const name of ['tipo_cnae', 'uf', 'municipio', 'bairro', 'nome', 'situacao', 'tipo_estabelecimento', 'porte', 'simples_nacional']) {
            const value = String(formData.get(name) || '').trim();
            if (value) params.set(name, value);
        }
        params.set('page', String(targetPage));
        params.set('limit', String(formData.get('limit') || 50));
        return `/api/empresas?${params.toString()}`;
    }

    async function search(targetPage = 1) {
        searchController?.abort();
        const controller = new AbortController();
        searchController = controller;
        searchError.hidden = true;
        setLoading(true);
        page = targetPage;

        try {
            const response = await fetch(buildSearchUrl(targetPage), { signal: controller.signal });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Não foi possível concluir a pesquisa.');

            const returnedPage = payload.pagination.page;
            totalPages = payload.pagination.totalPages ?? 0;
            if (totalPages > 0 && targetPage > totalPages) {
                return search(totalPages);
            }

            renderCompanies(payload.data);
            resultsStatus.hidden = payload.data.length > 0;
            resultsWrap.hidden = payload.data.length === 0;
            pagination.hidden = payload.data.length === 0 || totalPages <= 1;
            resultCount.textContent = payload.pagination.total == null
                ? `${payload.data.length} ${payload.data.length === 1 ? 'empresa nesta página' : 'empresas nesta página'}`
                : `${Number(payload.pagination.total).toLocaleString('pt-BR')} ${payload.pagination.total === 1 ? 'empresa encontrada' : 'empresas encontradas'}`;
            resultsStatus.dataset.kind = 'empty';
            resultsStatus.textContent = 'Nenhuma empresa encontrada para estes filtros.';
            pageLabel.textContent = `Página ${returnedPage} de ${totalPages}`;
            pageJumpInput.value = String(returnedPage);
            pageJumpInput.max = String(totalPages);
            totalPagesLabel.textContent = String(totalPages);
            previousButton.disabled = returnedPage <= 1;
            nextButton.disabled = returnedPage >= totalPages;
        } catch (error) {
            if (error.name === 'AbortError') return;
            resultsStatus.hidden = false;
            resultsStatus.dataset.kind = 'error';
            resultsStatus.textContent = 'A pesquisa não foi concluída.';
            resultCount.textContent = 'Falha na pesquisa';
            searchError.textContent = error.message;
            searchError.hidden = false;
        } finally {
            if (!controller.signal.aborted) setLoadingButton(false);
        }
    }

    function setLoadingButton(isLoading) {
        searchButton.disabled = isLoading;
        searchButton.querySelector('span').textContent = isLoading ? 'Pesquisando...' : 'Pesquisar empresas';
    }

    function addDetailRow(label, value, wide = false) {
        const row = document.createElement('div');
        row.className = wide ? 'detail-row detail-row-wide' : 'detail-row';
        const heading = document.createElement('span');
        heading.className = 'detail-label';
        heading.textContent = label;
        const content = document.createElement('span');
        content.className = 'detail-value';
        content.textContent = value || 'Não informado';
        row.append(heading, content);
        companyDetails.append(row);
    }

    async function openCompanyDetails(cnpj) {
        companyDetails.replaceChildren();
        dialogTitle.textContent = 'Carregando cadastro...';
        dialog.showModal();
        try {
            const response = await fetch(`/api/empresas/${encodeURIComponent(cnpj)}`);
            const company = await response.json();
            if (!response.ok) throw new Error(company.detail || 'Falha ao consultar o cadastro.');

            dialogTitle.textContent = company.razao_social || formatCnpj(company.cnpj);
            const address = [
                company.tipo_logradouro,
                company.logradouro,
                company.numero,
                company.complemento,
                company.bairro,
                company.municipio,
                company.uf,
                company.cep,
            ].filter(Boolean).join(', ');
            const secondaryCnaes = (company.cnaes_secundarios || []).join(', ');
            addDetailRow('CNPJ', formatCnpj(company.cnpj));
            addDetailRow('Nome fantasia', company.nome_fantasia);
            addDetailRow('Situação cadastral', company.situacao_cadastral);
            addDetailRow('Matriz ou filial', company.tipo_estabelecimento);
            addDetailRow('Início da atividade', formatDate(company.data_inicio_atividade));
            addDetailRow('CNAE principal', company.cnae_principal);
            addDetailRow('CNAEs secundários', secondaryCnaes, true);
            addDetailRow('Porte', company.porte);
            addDetailRow('Simples Nacional', company.simples_nacional == null ? 'Não informado' : company.simples_nacional ? 'Optante' : 'Não optante');
            addDetailRow('MEI', company.mei == null ? 'Não informado' : company.mei ? 'Optante' : 'Não optante');
            addDetailRow('Endereço', address, true);
            addDetailRow('E-mail', company.email, true);
            addDetailRow('Telefone', phoneText(company.telefones), true);
        } catch (error) {
            dialogTitle.textContent = 'Falha ao carregar cadastro';
            addDetailRow('Erro', error.message, true);
        }
    }

    async function lookupCnaes(term) {
        cnaeController?.abort();
        const controller = new AbortController();
        cnaeController = controller;
        cnaeLookupButton.disabled = true;
        cnaeLookupStatus.hidden = false;
        cnaeLookupStatus.textContent = 'Consultando CNAEs...';
        cnaeSuggestions.replaceChildren();
        cnaeSuggestions.hidden = true;
        try {
            const response = await fetch(`/api/cnaes?q=${encodeURIComponent(term)}&limit=20`, { signal: controller.signal });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.detail || 'Não foi possível pesquisar CNAEs.');
            if (!payload.length) {
                cnaeLookupStatus.textContent = 'Nenhum CNAE encontrado para esse termo.';
                return;
            }
            cnaeLookupStatus.hidden = true;
            for (const cnae of payload) {
                const item = document.createElement('li');
                const option = document.createElement('button');
                option.type = 'button';
                option.textContent = `${cnae.codigo} - ${cnae.descricao}`;
                option.addEventListener('click', () => {
                    const codes = String(cnaeInput.value || '')
                        .split(/[,;\n]+/)
                        .map((code) => code.trim())
                        .filter(Boolean);
                    if (!codes.includes(cnae.codigo)) codes.push(cnae.codigo);
                    cnaeInput.value = codes.join(', ');
                    cnaeLookupStatus.hidden = false;
                    cnaeLookupStatus.textContent = `CNAE ${cnae.codigo} adicionado aos filtros.`;
                    cnaeSuggestions.hidden = true;
                });
                item.append(option);
                cnaeSuggestions.append(item);
            }
            cnaeSuggestions.hidden = false;
        } catch (error) {
            if (error.name !== 'AbortError' && !controller.signal.aborted) {
                cnaeLookupStatus.hidden = false;
                cnaeLookupStatus.textContent = error.message;
            }
        } finally {
            if (!controller.signal.aborted) cnaeLookupButton.disabled = false;
        }
    }

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        search(1);
    });
    document.querySelector('#clear-filters').addEventListener('click', () => {
        form.reset();
        searchError.hidden = true;
        resultsBody.replaceChildren();
        resultsWrap.hidden = true;
        pagination.hidden = true;
        resultsStatus.hidden = false;
        resultsStatus.removeAttribute('data-kind');
        resultsStatus.textContent = 'Defina os filtros e pesquise para listar empresas.';
        resultCount.textContent = 'Aguardando pesquisa';
    });
    previousButton.addEventListener('click', () => {
        if (page > 1) search(page - 1);
    });
    nextButton.addEventListener('click', () => {
        if (page < totalPages) search(page + 1);
    });
    pageJumpForm.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!pageJumpInput.reportValidity()) return;
        const targetPage = Number(pageJumpInput.value);
        if (Number.isInteger(targetPage) && targetPage >= 1 && targetPage <= totalPages) {
            search(targetPage);
        }
    });
    cnaeLookupButton.addEventListener('click', () => {
        const term = cnaeLookupInput.value.trim();
        if (!term) {
            cnaeLookupStatus.hidden = false;
            cnaeLookupStatus.textContent = 'Digite um código ou nome de atividade para pesquisar.';
            return;
        }
        lookupCnaes(term);
    });
    document.querySelector('#close-dialog').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => {
        if (event.target === dialog) dialog.close();
    });
})();