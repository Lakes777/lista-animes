// Front da Lista de Animes: conversa com a própria API usando fetch().
// Todo texto vindo da API entra na página com textContent, que não interpreta HTML,
// então um título como "<script>..." aparece como texto e não é executado.

const estado = { status: "", busca: "", malIdsNaLista: new Set() };

const $ = (seletor) => document.querySelector(seletor);

// ---------- Conversa com a API ----------

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
  if (resposta.status === 204) return null;
  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) throw new Error(mensagemDeErro(dados, resposta.status));
  return dados;
}

function mensagemDeErro(dados, codigo) {
  const detalhe = dados?.detail;
  if (typeof detalhe === "string") return detalhe;
  // Erros de validação (422) vêm como lista; mostramos a primeira mensagem.
  if (Array.isArray(detalhe) && detalhe[0]?.msg) return detalhe[0].msg.replace("Value error, ", "");
  return `Algo deu errado (erro ${codigo}).`;
}

// ---------- Mensagens rápidas ----------

let temporizadorMensagem;

function mostrarMensagem(texto, erro = false) {
  const caixa = $("#mensagem");
  caixa.textContent = texto;
  caixa.classList.toggle("mensagem--erro", erro);
  caixa.hidden = false;
  clearTimeout(temporizadorMensagem);
  temporizadorMensagem = setTimeout(() => (caixa.hidden = true), 3500);
}

function mostrarAviso(elemento, texto) {
  elemento.textContent = texto;
  elemento.hidden = !texto;
}

// ---------- Estatísticas ----------

async function carregarEstatisticas() {
  const e = await api("/animes/estatisticas");
  const numeros = [
    [e.total, "animes na lista"],
    [e.por_status.assistindo, "assistindo"],
    [e.por_status.concluido, "concluídos"],
    [e.episodios_assistidos, "episódios vistos"],
    [e.nota_media ?? "—", "nota média"],
  ];
  $("#estatisticas").replaceChildren(
    ...numeros.map(([valor, rotulo]) => {
      const caixa = document.createElement("div");
      caixa.className = "numero";
      const v = document.createElement("span");
      v.className = "numero__valor";
      v.textContent = typeof valor === "number" ? valor.toLocaleString("pt-BR") : valor;
      const r = document.createElement("span");
      r.className = "numero__rotulo";
      r.textContent = rotulo;
      caixa.append(v, r);
      return caixa;
    }),
  );
}

// ---------- Minha lista ----------

function textoEpisodios(anime) {
  const total = anime.total_episodios ?? "?";
  return `${anime.episodios_vistos} / ${total} episódios`;
}

function preencherCapa(img, anime) {
  if (anime.imagem_url) {
    img.src = anime.imagem_url;
    img.alt = `Capa de ${anime.titulo}`;
  } else {
    img.removeAttribute("src");
  }
}

function criarCartaoAnime(anime) {
  const cartao = $("#molde-anime").content.firstElementChild.cloneNode(true);
  preencherCapa(cartao.querySelector(".cartao__capa"), anime);
  cartao.querySelector(".cartao__titulo").textContent = anime.titulo;
  cartao.querySelector(".episodios__texto").textContent = textoEpisodios(anime);

  const porcentagem = anime.total_episodios
    ? (100 * anime.episodios_vistos) / anime.total_episodios
    : 0;
  cartao.querySelector(".progresso__barra").style.width = `${porcentagem}%`;

  const status = cartao.querySelector('[data-campo="status"]');
  status.value = anime.status;
  status.addEventListener("change", () => editar(anime.id, { status: status.value }));

  const nota = cartao.querySelector('[data-campo="nota"]');
  for (let n = 10; n >= 1; n--) nota.add(new Option(String(n), String(n)));
  nota.value = anime.nota ?? "";
  nota.addEventListener("change", () =>
    editar(anime.id, { nota: nota.value ? Number(nota.value) : null }),
  );

  const mais1 = cartao.querySelector('[data-acao="mais1"]');
  const acabou = anime.total_episodios !== null && anime.episodios_vistos >= anime.total_episodios;
  mais1.disabled = acabou;
  mais1.addEventListener("click", () => {
    const vistos = anime.episodios_vistos + 1;
    const mudancas = { episodios_vistos: vistos };
    // Começou a ver? Vira "assistindo". Chegou ao último episódio? Vira "concluído".
    if (anime.status === "quero_ver") mudancas.status = "assistindo";
    if (anime.total_episodios !== null && vistos === anime.total_episodios) {
      mudancas.status = "concluido";
    }
    editar(anime.id, mudancas);
  });

  cartao.querySelector('[data-acao="remover"]').addEventListener("click", () => remover(anime));
  return cartao;
}

async function carregarLista() {
  const parametros = new URLSearchParams();
  if (estado.status) parametros.set("status", estado.status);
  if (estado.busca) parametros.set("busca", estado.busca);

  const animes = await api(`/animes?${parametros}`);
  $("#lista").replaceChildren(...animes.map(criarCartaoAnime));

  let aviso = "";
  if (animes.length === 0) {
    const filtrando = estado.status || estado.busca;
    aviso = filtrando
      ? "Nenhum anime com esse filtro."
      : "Sua lista está vazia. Busque um anime acima e clique em + Adicionar.";
  }
  mostrarAviso($("#aviso-lista"), aviso);
}

async function atualizarTudo() {
  // A lista completa (sem filtro) diz quais animes do catálogo já foram adicionados.
  const todos = await api("/animes");
  estado.malIdsNaLista = new Set(todos.map((a) => a.mal_id).filter(Boolean));
  await Promise.all([carregarLista(), carregarEstatisticas()]);
  marcarAdicionadosNoCatalogo();
}

async function editar(id, mudancas) {
  try {
    await api(`/animes/${id}`, { method: "PATCH", body: JSON.stringify(mudancas) });
    if (mudancas.status === "concluido") mostrarMensagem("🎉 Anime concluído!");
  } catch (erro) {
    mostrarMensagem(erro.message, true);
  }
  await atualizarTudo();
}

async function remover(anime) {
  if (!confirm(`Remover "${anime.titulo}" da sua lista?`)) return;
  try {
    await api(`/animes/${anime.id}`, { method: "DELETE" });
    mostrarMensagem(`"${anime.titulo}" saiu da lista.`);
  } catch (erro) {
    mostrarMensagem(erro.message, true);
  }
  await atualizarTudo();
}

// ---------- Catálogo (Jikan) ----------

function criarCartaoCatalogo(anime) {
  const cartao = $("#molde-catalogo").content.firstElementChild.cloneNode(true);
  cartao.dataset.malId = anime.mal_id;
  preencherCapa(cartao.querySelector(".cartao__capa"), anime);
  cartao.querySelector(".cartao__titulo").textContent = anime.titulo;

  const info = [
    anime.tipo,
    anime.ano,
    anime.total_episodios && `${anime.total_episodios} eps.`,
    anime.nota_mal && `⭐ ${anime.nota_mal}`,
  ].filter(Boolean);
  cartao.querySelector(".cartao__info").textContent = info.join(" · ");
  cartao.querySelector(".cartao__generos").textContent = anime.generos.slice(0, 3).join(", ");

  cartao.querySelector("button").addEventListener("click", async (evento) => {
    const botao = evento.currentTarget;
    botao.disabled = true;
    try {
      await api(`/animes/do-catalogo/${anime.mal_id}`, { method: "POST" });
      mostrarMensagem(`"${anime.titulo}" entrou na sua lista!`);
      await atualizarTudo();
    } catch (erro) {
      mostrarMensagem(erro.message, true);
      botao.disabled = false;
    }
  });
  return cartao;
}

function marcarAdicionadosNoCatalogo() {
  for (const cartao of $("#resultados-catalogo").children) {
    const jaNaLista = estado.malIdsNaLista.has(Number(cartao.dataset.malId));
    const botao = cartao.querySelector("button");
    botao.disabled = jaNaLista;
    botao.textContent = jaNaLista ? "✓ Na sua lista" : "+ Adicionar";
  }
}

async function buscarNoCatalogo(evento) {
  evento.preventDefault();
  const termo = $("#termo-catalogo").value.trim();
  const botao = evento.submitter;
  const aviso = $("#aviso-catalogo");

  botao.disabled = true;
  mostrarAviso(aviso, "Buscando no MyAnimeList...");
  try {
    const animes = await api(`/catalogo/busca?${new URLSearchParams({ q: termo })}`);
    $("#resultados-catalogo").replaceChildren(...animes.map(criarCartaoCatalogo));
    marcarAdicionadosNoCatalogo();
    mostrarAviso(aviso, animes.length ? "" : `Nenhum anime encontrado para "${termo}".`);
  } catch (erro) {
    $("#resultados-catalogo").replaceChildren();
    mostrarAviso(aviso, `⚠️ ${erro.message}`);
  } finally {
    botao.disabled = false;
  }
}

// ---------- Filtros ----------

function escolherAba(evento) {
  const aba = evento.target.closest(".aba");
  if (!aba) return;
  for (const outra of $("#abas").children) outra.classList.toggle("aba--ativa", outra === aba);
  estado.status = aba.dataset.status;
  carregarLista().catch((erro) => mostrarMensagem(erro.message, true));
}

let temporizadorFiltro;

function filtrarPorTitulo(evento) {
  // Espera a pessoa parar de digitar (300 ms) antes de consultar a API.
  clearTimeout(temporizadorFiltro);
  temporizadorFiltro = setTimeout(() => {
    estado.busca = evento.target.value.trim();
    carregarLista().catch((erro) => mostrarMensagem(erro.message, true));
  }, 300);
}

// ---------- Início ----------

$("#form-catalogo").addEventListener("submit", buscarNoCatalogo);
$("#abas").addEventListener("click", escolherAba);
$("#filtro-titulo").addEventListener("input", filtrarPorTitulo);

atualizarTudo().catch(() =>
  mostrarAviso($("#aviso-lista"), "⚠️ Não consegui falar com a API. Ela está rodando?"),
);
