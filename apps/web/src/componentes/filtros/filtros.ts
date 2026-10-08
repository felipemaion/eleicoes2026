import { ANOS, CARGOS, GRUPOS, UFS, type Filtros, type Store } from "../../store";

interface Campo<K extends keyof Filtros> {
  chave: K;
  rotulo: string;
  opcoes: readonly { valor: Filtros[K]; texto: string }[];
}

const doTipo = <K extends keyof Filtros>(c: Campo<K>): Campo<K> => c;

const CAMPOS = [
  doTipo({ chave: "uf", rotulo: "UF", opcoes: [{ valor: "BR", texto: "Brasil" }, ...UFS.map((u) => ({ valor: u, texto: u }))] }),
  doTipo({ chave: "cargo", rotulo: "Cargo", opcoes: CARGOS.map((c) => ({ valor: c, texto: c === "todos" ? "Todos" : c.replace(/_/g, " ") })) }),
  doTipo({ chave: "grupo", rotulo: "Grupo", opcoes: GRUPOS.map((g) => ({ valor: g, texto: g === "missao_2026" ? "Missão 2026" : "MBL 2022" })) }),
  doTipo({ chave: "ano", rotulo: "Ano", opcoes: ANOS.map((a) => ({ valor: a, texto: String(a) })) }),
];

/** Desenha os selects de filtro e mantém o valor exibido em sincronia com o store. */
export function render(container: HTMLElement, store: Store): void {
  const form = document.createElement("form");
  form.className = "filtros";
  form.setAttribute("aria-label", "Filtros");
  form.addEventListener("submit", (e) => { e.preventDefault(); });

  const selects = CAMPOS.map((campo) => {
    const label = document.createElement("label");
    label.append(campo.rotulo);
    const select = document.createElement("select");
    select.name = campo.chave;
    for (const o of campo.opcoes) select.add(new Option(o.texto, String(o.valor)));
    select.addEventListener("change", () => {
      const op = campo.opcoes.find((o) => String(o.valor) === select.value);
      if (op) store.definir({ [campo.chave]: op.valor });
    });
    label.append(select);
    form.append(label);
    return { campo, select };
  });

  const sincronizar = (): void => {
    const { filtros } = store.obter();
    for (const { campo, select } of selects) select.value = String(filtros[campo.chave]);
  };
  sincronizar();
  store.assinar(sincronizar);
  container.replaceChildren(form);
}
