import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime, timedelta
import calendar

import customtkinter as ctk
import psycopg2

try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None


ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


def sumar_meses(fecha, cantidad):
    mes_total = fecha.month - 1 + cantidad
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return fecha.replace(year=anio, month=mes, day=dia)


def sumar_anios(fecha, cantidad):
    anio = fecha.year + cantidad
    dia = min(fecha.day, calendar.monthrange(anio, fecha.month)[1])
    return fecha.replace(year=anio, day=dia)


def sumar_periodo(fecha, tipo_periodo, cantidad):
    if tipo_periodo == "Dias":
        return fecha + timedelta(days=cantidad)
    if tipo_periodo == "Semanas":
        return fecha + timedelta(weeks=cantidad)
    if tipo_periodo == "Meses":
        return sumar_meses(fecha, cantidad)
    if tipo_periodo == "A\u00f1os":
        return sumar_anios(fecha, cantidad)
    raise ValueError(f"tipo_periodo desconocido: {tipo_periodo}")


def generar_fechas_serie(fecha_inicio, tipo_periodo, cantidad, fecha_fin):
    if fecha_fin is None:
        fecha_fin = sumar_periodo(fecha_inicio, "Meses", 6)  # horizonte para series indefinidas
    fechas = []
    actual = fecha_inicio
    while actual <= fecha_fin:
        fechas.append(actual)
        actual = sumar_periodo(actual, tipo_periodo, cantidad)
    return fechas


class AppAgenda(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Agenda 3 Patitos")
        self.geometry("1280x760")
        self.minsize(1050, 650)

        self.conn_params = {
            "dbname": "agenda",
            "user": "postgres",
            "password": "andresbbello2006",
            "host": "localhost",
            "port": "5432", 
        }

        self.usuarios_combo = {}
        self.categorias_combo = {}
        self.categorias_padre_combo = {}
        self.tipos_disponibilidad_combo = {}

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.crear_sidebar()
        self.crear_area_principal()
        self.configurar_estilos()

        self.actualizar_todas_las_tablas()

        if DateEntry is None:
            self.after(500, lambda: messagebox.showwarning(
                "Calendario no instalado",
                "Para usar los selectores de fecha instala:\n\npip install tkcalendar"
            ))

    # -------------------- INFRAESTRUCTURA --------------------

    def obtener_conexion(self):
        conn = psycopg2.connect(**self.conn_params)
        conn.set_client_encoding("UTF8")
        with conn.cursor() as cur:
            cur.execute("SET search_path TO prototipo, public;")
        return conn

    def ejecutar_consulta(self, sql, params=None, fetch=False):
        conn = None
        try:
            conn = self.obtener_conexion()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() if fetch else None
            conn.commit()
            return rows
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def configurar_estilos(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=30, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))

    def crear_treeview(self, parent, columnas, widths):
        contenedor = ctk.CTkFrame(parent, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        tree = ttk.Treeview(contenedor, columns=columnas, show="headings")
        for col, width in zip(columnas, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="center")
        scroll_y = ttk.Scrollbar(contenedor, orient="vertical", command=tree.yview)
        scroll_x = ttk.Scrollbar(contenedor, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        contenedor.grid_rowconfigure(0, weight=1)
        contenedor.grid_columnconfigure(0, weight=1)
        return tree

    def seleccionar_modulo(self, nombre):
        self.tabview.set(nombre)
        for modulo, boton in self.botones_nav.items():
            boton.configure(fg_color=("gray75", "gray25") if modulo == nombre else "transparent")

    def crear_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=235, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)
        self.sidebar_frame.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(
            self.sidebar_frame,
            text="📅 AGENDA 🦆🦆🦆",
            font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(28, 5), sticky="w")

        ctk.CTkLabel(
            self.sidebar_frame,
            text="Gestión de usuarios, categorías y eventos",
            font=ctk.CTkFont(size=11),
            wraplength=190,
            justify="left"
        ).grid(row=1, column=0, padx=20, pady=(0, 25), sticky="w")

        self.botones_nav = {}
        for i, (nombre, icono) in enumerate([
            ("Usuarios", "👥"),
            ("Categorías", "📁"),
            ("Eventos", "🗓️"),
            ("Disponibilidad", "🕓"),
            ("Eventos Recurrentes", "🔁"),
        ], start=2):
            btn = ctk.CTkButton(
                self.sidebar_frame, text=f"{icono}  {nombre}",
                anchor="w", fg_color="transparent",
                command=lambda n=nombre: self.seleccionar_modulo(n)
            )
            btn.grid(row=i, column=0, padx=15, pady=5, sticky="ew")
            self.botones_nav[nombre] = btn

        ctk.CTkButton(
            self.sidebar_frame,
            text="🔄  Recargar datos",
            command=self.actualizar_todas_las_tablas
        ).grid(row=7, column=0, padx=15, pady=(20, 5), sticky="ew")

        ctk.CTkLabel(self.sidebar_frame, text="APARIENCIA", font=ctk.CTkFont(size=11, weight="bold")).grid(
            row=11, column=0, padx=20, pady=(10, 5), sticky="w"
        )
        self.option_mode = ctk.CTkOptionMenu(
            self.sidebar_frame,
            values=["System", "Dark", "Light"],
            command=ctk.set_appearance_mode
        )
        self.option_mode.set("System")
        self.option_mode.grid(row=12, column=0, padx=15, pady=(0, 25), sticky="ew")

    def crear_area_principal(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self.main_container, command=self.al_cambiar_pestana)
        self.tabview.grid(row=0, column=0, sticky="nsew")

        self.tab_usuarios = self.tabview.add("Usuarios")
        self.tab_categorias = self.tabview.add("Categorías")
        self.tab_eventos = self.tabview.add("Eventos")
        self.tab_disponibilidades = self.tabview.add("Disponibilidad")
        self.tab_series = self.tabview.add("Eventos Recurrentes")

        self.configurar_pestana_usuarios()
        self.configurar_pestana_categorias()
        self.configurar_pestana_eventos()
        self.configurar_pestana_disponibilidades()
        self.configurar_pestana_series()
        self.seleccionar_modulo("Usuarios")

    def al_cambiar_pestana(self):
        nombre = self.tabview.get()
        if nombre in self.botones_nav:
            for modulo, boton in self.botones_nav.items():
                boton.configure(fg_color=("gray75", "gray25") if modulo == nombre else "transparent")

    def crear_encabezado(self, parent, titulo, descripcion):
        ctk.CTkLabel(parent, text=titulo, font=ctk.CTkFont(size=24, weight="bold")).pack(
            anchor="w", padx=15, pady=(15, 0)
        )
        ctk.CTkLabel(parent, text=descripcion, font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=15, pady=(0, 12)
        )

    # -------------------- USUARIOS --------------------

    def configurar_pestana_usuarios(self):
        self.crear_encabezado(self.tab_usuarios, "Usuarios", "Registra, consulta y administra los usuarios de la agenda.")

        cuerpo = ctk.CTkFrame(self.tab_usuarios, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=10, pady=5)
        cuerpo.grid_columnconfigure(0, weight=3)
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)

        tabla_frame = ctk.CTkFrame(cuerpo)
        tabla_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form = ctk.CTkScrollableFrame(cuerpo, width=300)
        form.grid(row=0, column=1, sticky="nsew")

        self.tree_usuarios = self.crear_treeview(
            tabla_frame, ("ID", "Nombre", "Apellido", "Registro", "Activo"),
            (70, 160, 160, 160, 80)
        )
        self.tree_usuarios.bind("<<TreeviewSelect>>", self.cargar_usuario_seleccionado)

        ctk.CTkLabel(form, text="Formulario de usuario", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 15))
        self.entry_nombre = ctk.CTkEntry(form, placeholder_text="Nombre")
        self.entry_nombre.pack(fill="x", padx=10, pady=6)
        self.entry_apellido = ctk.CTkEntry(form, placeholder_text="Apellido")
        self.entry_apellido.pack(fill="x", padx=10, pady=6)

        self.switch_usuario_activo = ctk.CTkSwitch(form, text="Usuario activo")
        self.switch_usuario_activo.select()
        self.switch_usuario_activo.pack(anchor="w", padx=12, pady=10)

        ctk.CTkButton(form, text="➕ Registrar usuario", command=self.agregar_usuario).pack(fill="x", padx=10, pady=(12, 5))
        ctk.CTkButton(form, text="💾 Actualizar seleccionado", command=self.actualizar_usuario).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🧹 Nuevo / Limpiar", command=self.limpiar_form_usuario, fg_color="gray").pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🗑️ Eliminar seleccionado", command=self.eliminar_usuario, fg_color="#b33939", hover_color="#8f2d2d").pack(fill="x", padx=10, pady=5)

    def usuario_seleccionado_id(self):
        sel = self.tree_usuarios.selection()
        return self.tree_usuarios.item(sel[0])["values"][0] if sel else None

    def cargar_usuario_seleccionado(self, _=None):
        sel = self.tree_usuarios.selection()
        if not sel:
            return
        vals = self.tree_usuarios.item(sel[0])["values"]
        self.entry_nombre.delete(0, tk.END); self.entry_nombre.insert(0, vals[1])
        self.entry_apellido.delete(0, tk.END); self.entry_apellido.insert(0, vals[2])
        if vals[4]:
            self.switch_usuario_activo.select()
        else:
            self.switch_usuario_activo.deselect()

    def limpiar_form_usuario(self):
        self.tree_usuarios.selection_remove(self.tree_usuarios.selection())
        self.entry_nombre.delete(0, tk.END)
        self.entry_apellido.delete(0, tk.END)
        self.switch_usuario_activo.select()

    def agregar_usuario(self):
        nombre, apellido = self.entry_nombre.get().strip(), self.entry_apellido.get().strip()
        if not nombre or not apellido:
            return messagebox.showwarning("Campos incompletos", "Indica nombre y apellido.")
        try:
            self.ejecutar_consulta("INSERT INTO usuarios (nombre, apellido, activo) VALUES (%s, %s, %s)",
                                   (nombre, apellido, self.switch_usuario_activo.get() == 1))
            self.limpiar_form_usuario(); self.actualizar_todas_las_tablas()
            messagebox.showinfo("Éxito", "Usuario registrado correctamente.")
        except Exception as e:
            messagebox.showerror("Error de base de datos", str(e))

    def actualizar_usuario(self):
        uid = self.usuario_seleccionado_id()
        if uid is None:
            return messagebox.showwarning("Selección requerida", "Selecciona un usuario para actualizar.")
        nombre, apellido = self.entry_nombre.get().strip(), self.entry_apellido.get().strip()
        if not nombre or not apellido:
            return messagebox.showwarning("Campos incompletos", "Indica nombre y apellido.")
        try:
            self.ejecutar_consulta("UPDATE usuarios SET nombre=%s, apellido=%s, activo=%s WHERE id_usuario=%s",
                                   (nombre, apellido, self.switch_usuario_activo.get() == 1, uid))
            self.actualizar_todas_las_tablas()
            messagebox.showinfo("Éxito", "Usuario actualizado.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def eliminar_usuario(self):
        uid = self.usuario_seleccionado_id()
        if uid is None:
            return messagebox.showwarning("Selección requerida", "Selecciona un usuario.")
        if not messagebox.askyesno("Confirmar", "¿Eliminar el usuario seleccionado?"):
            return
        try:
            self.ejecutar_consulta("DELETE FROM usuarios WHERE id_usuario=%s", (uid,))
            self.limpiar_form_usuario(); self.actualizar_todas_las_tablas()
            messagebox.showinfo("Eliminado", "Usuario eliminado.")
        except Exception as e:
            messagebox.showerror("No se pudo eliminar", str(e))

    def cargar_datos_usuarios(self):
        try:
            rows = self.ejecutar_consulta(
                "SELECT id_usuario, nombre, apellido, fecha_registro, activo FROM usuarios ORDER BY nombre, apellido",
                fetch=True
            )
            for item in self.tree_usuarios.get_children(): self.tree_usuarios.delete(item)
            self.usuarios_combo = {}
            for row in rows:
                registro = row[3].strftime("%Y-%m-%d %H:%M") if hasattr(row[3], "strftime") else row[3]
                self.tree_usuarios.insert("", "end", values=(row[0], row[1], row[2], registro, "Sí" if row[4] else "No"))
                etiqueta = f"{row[1]} {row[2]} — #{row[0]}"
                self.usuarios_combo[etiqueta] = row[0]
        except Exception as e:
            print(f"Error cargando usuarios: {e}")

    # -------------------- CATEGORÍAS --------------------

    def configurar_pestana_categorias(self):
        self.crear_encabezado(self.tab_categorias, "Categorías", "Organiza los eventos mediante categorías y subcategorías.")

        cuerpo = ctk.CTkFrame(self.tab_categorias, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=10, pady=5)
        cuerpo.grid_columnconfigure(0, weight=3); cuerpo.grid_columnconfigure(1, weight=1); cuerpo.grid_rowconfigure(0, weight=1)

        tabla = ctk.CTkFrame(cuerpo); tabla.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form = ctk.CTkScrollableFrame(cuerpo, width=320); form.grid(row=0, column=1, sticky="nsew")

        self.tree_categorias = self.crear_treeview(tabla, ("ID", "Categoría", "Categoría padre"), (80, 230, 230))
        self.tree_categorias.bind("<<TreeviewSelect>>", self.cargar_categoria_seleccionada)

        ctk.CTkLabel(form, text="Formulario de categoría", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 15))
        self.entry_cat_nombre = ctk.CTkEntry(form, placeholder_text="Nombre de la categoría")
        self.entry_cat_nombre.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(form, text="Categoría padre").pack(anchor="w", padx=10, pady=(10, 2))
        self.combo_cat_padre = ctk.CTkComboBox(form, values=["Sin categoría padre"], state="readonly")
        self.combo_cat_padre.set("Sin categoría padre")
        self.combo_cat_padre.pack(fill="x", padx=10, pady=6)

        ctk.CTkButton(form, text="➕ Crear categoría", command=self.agregar_categoria).pack(fill="x", padx=10, pady=(15, 5))
        ctk.CTkButton(form, text="💾 Actualizar seleccionada", command=self.actualizar_categoria).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🧹 Nueva / Limpiar", command=self.limpiar_form_categoria, fg_color="gray").pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🗑️ Eliminar seleccionada", command=self.eliminar_categoria, fg_color="#b33939", hover_color="#8f2d2d").pack(fill="x", padx=10, pady=5)

    def categoria_seleccionada_id(self):
        sel = self.tree_categorias.selection()
        return self.tree_categorias.item(sel[0])["values"][0] if sel else None

    def cargar_categoria_seleccionada(self, _=None):
        sel = self.tree_categorias.selection()
        if not sel: return
        vals = self.tree_categorias.item(sel[0])["values"]
        self.entry_cat_nombre.delete(0, tk.END); self.entry_cat_nombre.insert(0, vals[1])
        padre = vals[2]
        self.combo_cat_padre.set(padre if padre in self.categorias_padre_combo else "Sin categoría padre")

    def limpiar_form_categoria(self):
        self.tree_categorias.selection_remove(self.tree_categorias.selection())
        self.entry_cat_nombre.delete(0, tk.END); self.combo_cat_padre.set("Sin categoría padre")

    def _padre_id_actual(self):
        valor = self.combo_cat_padre.get()
        return None if valor == "Sin categoría padre" else self.categorias_padre_combo.get(valor)

    def agregar_categoria(self):
        nombre = self.entry_cat_nombre.get().strip()
        if not nombre: return messagebox.showwarning("Campo requerido", "Indica el nombre de la categoría.")
        try:
            self.ejecutar_consulta("INSERT INTO categorias (nombre, id_categoria_padre) VALUES (%s, %s)",
                                   (nombre, self._padre_id_actual()))
            self.limpiar_form_categoria(); self.actualizar_todas_las_tablas()
            messagebox.showinfo("Éxito", "Categoría creada.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def actualizar_categoria(self):
        cid = self.categoria_seleccionada_id()
        if cid is None: return messagebox.showwarning("Selección requerida", "Selecciona una categoría.")
        nombre = self.entry_cat_nombre.get().strip(); padre = self._padre_id_actual()
        if not nombre: return messagebox.showwarning("Campo requerido", "Indica el nombre.")
        if padre == cid: return messagebox.showwarning("Relación inválida", "Una categoría no puede ser su propia categoría padre.")
        try:
            self.ejecutar_consulta("UPDATE categorias SET nombre=%s, id_categoria_padre=%s WHERE id_categoria=%s",
                                   (nombre, padre, cid))
            self.actualizar_todas_las_tablas(); messagebox.showinfo("Éxito", "Categoría actualizada.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def eliminar_categoria(self):
        cid = self.categoria_seleccionada_id()
        if cid is None: return messagebox.showwarning("Selección requerida", "Selecciona una categoría.")
        if not messagebox.askyesno("Confirmar", "¿Eliminar la categoría seleccionada?"): return
        try:
            self.ejecutar_consulta("DELETE FROM categorias WHERE id_categoria=%s", (cid,))
            self.limpiar_form_categoria(); self.actualizar_todas_las_tablas()
            messagebox.showinfo("Eliminado", "Categoría eliminada.")
        except Exception as e:
            messagebox.showerror("No se pudo eliminar", str(e))

    def cargar_datos_categorias(self):
        try:
            rows = self.ejecutar_consulta("""
                SELECT c.id_categoria, c.nombre, p.nombre
                FROM categorias c
                LEFT JOIN categorias p ON p.id_categoria = c.id_categoria_padre
                ORDER BY c.nombre
            """, fetch=True)
            ids = self.ejecutar_consulta("SELECT id_categoria, nombre FROM categorias ORDER BY nombre", fetch=True)

            for item in self.tree_categorias.get_children(): self.tree_categorias.delete(item)
            self.categorias_combo = {}
            self.categorias_padre_combo = {}
            for cid, nombre in ids:
                etiqueta = f"{nombre} — #{cid}"
                self.categorias_combo[etiqueta] = cid
                self.categorias_padre_combo[etiqueta] = cid
            for row in rows:
                padre = "Sin categoría padre"
                if row[2] is not None:
                    # Buscar etiqueta completa del padre
                    for etiqueta, cid in self.categorias_padre_combo.items():
                        if etiqueta.startswith(f"{row[2]} —"):
                            padre = etiqueta; break
                self.tree_categorias.insert("", "end", values=(row[0], row[1], padre))

            valores_padre = ["Sin categoría padre"] + list(self.categorias_padre_combo.keys())
            self.combo_cat_padre.configure(values=valores_padre)
            if self.combo_cat_padre.get() not in valores_padre:
                self.combo_cat_padre.set("Sin categoría padre")
        except Exception as e:
            print(f"Error cargando categorías: {e}")

    # -------------------- EVENTOS --------------------

    def configurar_pestana_eventos(self):
        self.crear_encabezado(self.tab_eventos, "Eventos", "Programa eventos seleccionando usuarios, categorías, fechas y horas.")

        cuerpo = ctk.CTkFrame(self.tab_eventos, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=10, pady=5)
        cuerpo.grid_columnconfigure(0, weight=3); cuerpo.grid_columnconfigure(1, weight=1); cuerpo.grid_rowconfigure(0, weight=1)

        tabla = ctk.CTkFrame(cuerpo); tabla.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form = ctk.CTkScrollableFrame(cuerpo, width=350); form.grid(row=0, column=1, sticky="nsew")

        self.tree_eventos = self.crear_treeview(
            tabla, ("ID", "Propietario", "Categoría", "Título", "Inicio", "Fin"),
            (70, 170, 150, 220, 150, 150)
        )
        self.tree_eventos.bind("<<TreeviewSelect>>", self.cargar_evento_seleccionado)

        ctk.CTkLabel(form, text="Formulario de evento", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 12))

        self.entry_ev_titulo = ctk.CTkEntry(form, placeholder_text="Título del evento")
        self.entry_ev_titulo.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(form, text="Propietario").pack(anchor="w", padx=10, pady=(8, 2))
        self.combo_ev_usuario = ctk.CTkComboBox(form, values=["Seleccione un usuario"], state="readonly")
        self.combo_ev_usuario.set("Seleccione un usuario")
        self.combo_ev_usuario.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Categoría").pack(anchor="w", padx=10, pady=(8, 2))
        self.combo_ev_categoria = ctk.CTkComboBox(form, values=["Seleccione una categoría"], state="readonly")
        self.combo_ev_categoria.set("Seleccione una categoría")
        self.combo_ev_categoria.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Inicio").pack(anchor="w", padx=10, pady=(10, 2))
        fila_inicio = ctk.CTkFrame(form, fg_color="transparent"); fila_inicio.pack(fill="x", padx=10)
        self.fecha_inicio = self.crear_selector_fecha(fila_inicio)
        self.fecha_inicio.pack(side="left", fill="x", expand=True)
        self.hora_inicio = ctk.CTkEntry(fila_inicio, placeholder_text="HH:MM", width=75)
        self.hora_inicio.pack(side="left", padx=(6, 0))

        ctk.CTkLabel(form, text="Fin").pack(anchor="w", padx=10, pady=(10, 2))
        fila_fin = ctk.CTkFrame(form, fg_color="transparent"); fila_fin.pack(fill="x", padx=10)
        self.fecha_fin = self.crear_selector_fecha(fila_fin)
        self.fecha_fin.pack(side="left", fill="x", expand=True)
        self.hora_fin = ctk.CTkEntry(fila_fin, placeholder_text="HH:MM", width=75)
        self.hora_fin.pack(side="left", padx=(6, 0))

        ctk.CTkButton(form, text="➕ Crear evento", command=self.agregar_evento).pack(fill="x", padx=10, pady=(16, 5))
        ctk.CTkButton(form, text="💾 Actualizar seleccionado", command=self.actualizar_evento).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🧹 Nuevo / Limpiar", command=self.limpiar_form_evento, fg_color="gray").pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🗑️ Eliminar seleccionado", command=self.eliminar_evento, fg_color="#b33939", hover_color="#8f2d2d").pack(fill="x", padx=10, pady=5)

        self.limpiar_form_evento()

    def crear_selector_fecha(self, parent):
        if DateEntry is not None:
            return DateEntry(parent, date_pattern="yyyy-mm-dd", font=("Arial", 10))
        return ttk.Entry(parent)

    def obtener_fecha(self, widget):
        if DateEntry is not None:
            return widget.get_date().strftime("%Y-%m-%d")
        return widget.get().strip()

    def establecer_fecha(self, widget, valor):
        fecha = valor.date() if hasattr(valor, "date") else datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
        if DateEntry is not None:
            widget.set_date(fecha)
        else:
            widget.delete(0, tk.END); widget.insert(0, fecha.strftime("%Y-%m-%d"))

    def evento_seleccionado_id(self):
        sel = self.tree_eventos.selection()
        return self.tree_eventos.item(sel[0])["values"][0] if sel else None

    def cargar_evento_seleccionado(self, _=None):
        sel = self.tree_eventos.selection()
        if not sel: return
        vals = self.tree_eventos.item(sel[0])["values"]
        self.entry_ev_titulo.delete(0, tk.END); self.entry_ev_titulo.insert(0, vals[3])
        self.combo_ev_usuario.set(vals[1])
        self.combo_ev_categoria.set(vals[2])
        try:
            ini = datetime.strptime(str(vals[4]), "%Y-%m-%d %H:%M")
            fin = datetime.strptime(str(vals[5]), "%Y-%m-%d %H:%M")
            self.establecer_fecha(self.fecha_inicio, ini)
            self.establecer_fecha(self.fecha_fin, fin)
            self.hora_inicio.delete(0, tk.END); self.hora_inicio.insert(0, ini.strftime("%H:%M"))
            self.hora_fin.delete(0, tk.END); self.hora_fin.insert(0, fin.strftime("%H:%M"))
        except ValueError:
            pass

    def limpiar_form_evento(self):
        self.tree_eventos.selection_remove(self.tree_eventos.selection())
        self.entry_ev_titulo.delete(0, tk.END)
        self.combo_ev_usuario.set("Seleccione un usuario")
        self.combo_ev_categoria.set("Seleccione una categoría")
        hoy = datetime.now()
        self.establecer_fecha(self.fecha_inicio, hoy); self.establecer_fecha(self.fecha_fin, hoy)
        self.hora_inicio.delete(0, tk.END); self.hora_inicio.insert(0, "09:00")
        self.hora_fin.delete(0, tk.END); self.hora_fin.insert(0, "10:00")

    def datos_evento_formulario(self):
        titulo = self.entry_ev_titulo.get().strip()
        usuario = self.usuarios_combo.get(self.combo_ev_usuario.get())
        categoria = self.categorias_combo.get(self.combo_ev_categoria.get())
        try:
            inicio = datetime.strptime(f"{self.obtener_fecha(self.fecha_inicio)} {self.hora_inicio.get().strip()}", "%Y-%m-%d %H:%M")
            fin = datetime.strptime(f"{self.obtener_fecha(self.fecha_fin)} {self.hora_fin.get().strip()}", "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError("La hora debe tener formato HH:MM, por ejemplo 09:30.")
        if not titulo or usuario is None or categoria is None:
            raise ValueError("Completa título, propietario y categoría.")
        if fin <= inicio:
            raise ValueError("La fecha y hora de finalización deben ser posteriores al inicio.")
        return usuario, categoria, titulo, inicio, fin

    def agregar_evento(self):
        try:
            datos = self.datos_evento_formulario()
            self.ejecutar_consulta("""
                INSERT INTO eventos
                (id_usuario_propietario, id_categoria, titulo, fecha_inicio, fecha_fin)
                VALUES (%s, %s, %s, %s, %s)
            """, datos)
            self.limpiar_form_evento(); self.cargar_datos_eventos()
            messagebox.showinfo("Éxito", "Evento creado correctamente.")
        except Exception as e:
            messagebox.showerror("No se pudo crear el evento", str(e))

    def actualizar_evento(self):
        eid = self.evento_seleccionado_id()
        if eid is None: return messagebox.showwarning("Selección requerida", "Selecciona un evento.")
        try:
            usuario, categoria, titulo, inicio, fin = self.datos_evento_formulario()
            self.ejecutar_consulta("""
                UPDATE eventos SET id_usuario_propietario=%s, id_categoria=%s,
                titulo=%s, fecha_inicio=%s, fecha_fin=%s WHERE id_evento=%s
            """, (usuario, categoria, titulo, inicio, fin, eid))
            self.cargar_datos_eventos(); messagebox.showinfo("Éxito", "Evento actualizado.")
        except Exception as e:
            messagebox.showerror("No se pudo actualizar", str(e))

    def eliminar_evento(self):
        eid = self.evento_seleccionado_id()
        if eid is None: return messagebox.showwarning("Selección requerida", "Selecciona un evento.")
        if not messagebox.askyesno("Confirmar", "¿Eliminar el evento seleccionado?"): return
        try:
            self.ejecutar_consulta("DELETE FROM eventos WHERE id_evento=%s", (eid,))
            self.limpiar_form_evento(); self.cargar_datos_eventos()
            messagebox.showinfo("Eliminado", "Evento eliminado.")
        except Exception as e:
            messagebox.showerror("No se pudo eliminar", str(e))

    def cargar_datos_eventos(self):
        try:
            rows = self.ejecutar_consulta("""
                SELECT e.id_evento, u.id_usuario, u.nombre, u.apellido,
                       c.id_categoria, c.nombre, e.titulo, e.fecha_inicio, e.fecha_fin
                FROM eventos e
                JOIN usuarios u ON u.id_usuario = e.id_usuario_propietario
                JOIN categorias c ON c.id_categoria = e.id_categoria
                ORDER BY e.fecha_inicio DESC
            """, fetch=True)
            for item in self.tree_eventos.get_children(): self.tree_eventos.delete(item)
            for row in rows:
                usuario = f"{row[2]} {row[3]} — #{row[1]}"
                categoria = f"{row[5]} — #{row[4]}"
                inicio = row[7].strftime("%Y-%m-%d %H:%M") if hasattr(row[7], "strftime") else row[7]
                fin = row[8].strftime("%Y-%m-%d %H:%M") if hasattr(row[8], "strftime") else row[8]
                self.tree_eventos.insert("", "end", values=(row[0], usuario, categoria, row[6], inicio, fin))

            valores_u = ["Seleccione un usuario"] + list(self.usuarios_combo.keys())
            valores_c = ["Seleccione una categoría"] + list(self.categorias_combo.keys())
            self.combo_ev_usuario.configure(values=valores_u)
            self.combo_ev_categoria.configure(values=valores_c)
        except Exception as e:
            print(f"Error cargando eventos: {e}")

    # -------------------- DISPONIBILIDAD --------------------

    def configurar_pestana_disponibilidades(self):
        self.crear_encabezado(self.tab_disponibilidades, "Disponibilidad",
                               "Registra tus franjas de tiempo libres, ocupadas o no disponibles.")

        cuerpo = ctk.CTkFrame(self.tab_disponibilidades, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=10, pady=5)
        cuerpo.grid_columnconfigure(0, weight=3)
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=2)
        cuerpo.grid_rowconfigure(1, weight=1)

        tabla = ctk.CTkFrame(cuerpo)
        tabla.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))

        form = ctk.CTkScrollableFrame(cuerpo, width=300)
        form.grid(row=0, column=1, sticky="nsew", pady=(0, 8))

        self.tree_disponibilidades = self.crear_treeview(
            tabla,
            ("ID", "Usuario", "Tipo", "Fecha", "Inicio", "Fin"),
            (60, 170, 120, 100, 80, 80)
        )
        self.tree_disponibilidades.bind("<<TreeviewSelect>>", self.cargar_disponibilidad_seleccionada)

        ctk.CTkLabel(form, text="Formulario de disponibilidad",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 15))

        ctk.CTkLabel(form, text="Usuario").pack(anchor="w", padx=10, pady=(8, 2))
        self.combo_disp_usuario = ctk.CTkComboBox(form, values=["Seleccione un usuario"], state="readonly")
        self.combo_disp_usuario.set("Seleccione un usuario")
        self.combo_disp_usuario.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Tipo de disponibilidad").pack(anchor="w", padx=10, pady=(8, 2))
        self.combo_disp_tipo = ctk.CTkComboBox(form, values=["Seleccione un tipo"], state="readonly")
        self.combo_disp_tipo.set("Seleccione un tipo")
        self.combo_disp_tipo.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Fecha").pack(anchor="w", padx=10, pady=(10, 2))
        self.fecha_disp = self.crear_selector_fecha(form)
        self.fecha_disp.pack(fill="x", padx=10)

        ctk.CTkLabel(form, text="Hora inicio (HH:MM)").pack(anchor="w", padx=10, pady=(10, 2))
        self.hora_inicio_disp = ctk.CTkEntry(form, placeholder_text="HH:MM")
        self.hora_inicio_disp.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Hora fin (HH:MM)").pack(anchor="w", padx=10, pady=(10, 2))
        self.hora_fin_disp = ctk.CTkEntry(form, placeholder_text="HH:MM")
        self.hora_fin_disp.pack(fill="x", padx=10, pady=4)

        ctk.CTkButton(form, text="➕ Registrar franja",
                      command=self.agregar_disponibilidad).pack(fill="x", padx=10, pady=(16, 5))
        ctk.CTkButton(form, text="💾 Actualizar seleccionada",
                      command=self.actualizar_disponibilidad).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🧹 Nueva / Limpiar",
                      command=self.limpiar_form_disponibilidad, fg_color="gray").pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(form, text="🗑️ Eliminar seleccionada",
                      command=self.eliminar_disponibilidad, fg_color="#b33939",
                      hover_color="#8f2d2d").pack(fill="x", padx=10, pady=5)

        self.limpiar_form_disponibilidad()

        # -------- RF-12: buscar quién está libre en un rango --------
        busqueda = ctk.CTkFrame(cuerpo)
        busqueda.grid(row=1, column=0, columnspan=2, sticky="nsew")

        ctk.CTkLabel(busqueda, text="¿Quién está libre en un rango de tiempo?",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))

        controles = ctk.CTkFrame(busqueda, fg_color="transparent")
        controles.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(controles, text="Fecha").grid(row=0, column=0, padx=(0, 6), sticky="w")
        self.fecha_busqueda = self.crear_selector_fecha(controles)
        self.fecha_busqueda.grid(row=1, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkLabel(controles, text="Hora inicio").grid(row=0, column=1, padx=6, sticky="w")
        self.hora_inicio_busqueda = ctk.CTkEntry(controles, placeholder_text="HH:MM", width=90)
        self.hora_inicio_busqueda.grid(row=1, column=1, padx=6, sticky="ew")

        ctk.CTkLabel(controles, text="Hora fin").grid(row=0, column=2, padx=6, sticky="w")
        self.hora_fin_busqueda = ctk.CTkEntry(controles, placeholder_text="HH:MM", width=90)
        self.hora_fin_busqueda.grid(row=1, column=2, padx=6, sticky="ew")

        ctk.CTkButton(controles, text="🔎 Buscar disponibles",
                      command=self.buscar_usuarios_libres).grid(row=1, column=3, padx=(12, 0), sticky="ew")

        self.tree_libres = self.crear_treeview(busqueda, ("ID", "Usuario"), (60, 220))

    def disponibilidad_seleccionada_id(self):
        sel = self.tree_disponibilidades.selection()
        return self.tree_disponibilidades.item(sel[0])["values"][0] if sel else None

    def cargar_disponibilidad_seleccionada(self, _=None):
        sel = self.tree_disponibilidades.selection()
        if not sel:
            return
        vals = self.tree_disponibilidades.item(sel[0])["values"]
        self.combo_disp_usuario.set(vals[1])
        self.combo_disp_tipo.set(vals[2])
        try:
            fecha = datetime.strptime(str(vals[3]), "%Y-%m-%d")
            self.establecer_fecha(self.fecha_disp, fecha)
        except ValueError:
            pass
        self.hora_inicio_disp.delete(0, tk.END); self.hora_inicio_disp.insert(0, str(vals[4]))
        self.hora_fin_disp.delete(0, tk.END); self.hora_fin_disp.insert(0, str(vals[5]))

    def limpiar_form_disponibilidad(self):
        self.tree_disponibilidades.selection_remove(self.tree_disponibilidades.selection())
        self.combo_disp_usuario.set("Seleccione un usuario")
        self.combo_disp_tipo.set("Seleccione un tipo")
        self.establecer_fecha(self.fecha_disp, datetime.now())
        self.hora_inicio_disp.delete(0, tk.END); self.hora_inicio_disp.insert(0, "09:00")
        self.hora_fin_disp.delete(0, tk.END); self.hora_fin_disp.insert(0, "10:00")

    def datos_disponibilidad_formulario(self):
        usuario = self.usuarios_combo.get(self.combo_disp_usuario.get())
        tipo = self.tipos_disponibilidad_combo.get(self.combo_disp_tipo.get())
        fecha = self.obtener_fecha(self.fecha_disp)
        try:
            inicio = datetime.strptime(self.hora_inicio_disp.get().strip(), "%H:%M").time()
            fin = datetime.strptime(self.hora_fin_disp.get().strip(), "%H:%M").time()
        except ValueError:
            raise ValueError("La hora debe tener formato HH:MM, por ejemplo 09:30.")

        if usuario is None or tipo is None:
            raise ValueError("Selecciona un usuario y un tipo de disponibilidad.")
        if fin <= inicio:
            raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")

        return usuario, tipo, fecha, inicio, fin

    def agregar_disponibilidad(self):
        try:
            datos = self.datos_disponibilidad_formulario()
            self.ejecutar_consulta("""
                INSERT INTO disponibilidades
                (id_usuario, id_tipo_disponibilidad, fecha, hora_inicio, hora_fin)
                VALUES (%s, %s, %s, %s, %s)
            """, datos)
            self.limpiar_form_disponibilidad(); self.cargar_datos_disponibilidades()
            messagebox.showinfo("Éxito", "Franja de disponibilidad registrada.")
        except Exception as e:
            messagebox.showerror("No se pudo registrar", str(e))

    def actualizar_disponibilidad(self):
        did = self.disponibilidad_seleccionada_id()
        if did is None:
            return messagebox.showwarning("Selección requerida", "Selecciona una franja.")
        try:
            usuario, tipo, fecha, inicio, fin = self.datos_disponibilidad_formulario()
            self.ejecutar_consulta("""
                UPDATE disponibilidades SET id_usuario=%s, id_tipo_disponibilidad=%s,
                fecha=%s, hora_inicio=%s, hora_fin=%s WHERE id_disponibilidad=%s
            """, (usuario, tipo, fecha, inicio, fin, did))
            self.cargar_datos_disponibilidades()
            messagebox.showinfo("Éxito", "Franja actualizada.")
        except Exception as e:
            messagebox.showerror("No se pudo actualizar", str(e))

    def eliminar_disponibilidad(self):
        did = self.disponibilidad_seleccionada_id()
        if did is None:
            return messagebox.showwarning("Selección requerida", "Selecciona una franja.")
        if not messagebox.askyesno("Confirmar", "¿Eliminar la franja seleccionada?"):
            return
        try:
            self.ejecutar_consulta("DELETE FROM disponibilidades WHERE id_disponibilidad=%s", (did,))
            self.limpiar_form_disponibilidad(); self.cargar_datos_disponibilidades()
            messagebox.showinfo("Eliminado", "Franja eliminada.")
        except Exception as e:
            messagebox.showerror("No se pudo eliminar", str(e))

    def cargar_datos_disponibilidades(self):
        try:
            rows = self.ejecutar_consulta("""
                SELECT d.id_disponibilidad, u.id_usuario, u.nombre, u.apellido,
                       t.id_tipo_disponibilidad, t.estado, d.fecha, d.hora_inicio, d.hora_fin
                FROM disponibilidades d
                JOIN usuarios u ON u.id_usuario = d.id_usuario
                JOIN tipos_disponibilidad t ON t.id_tipo_disponibilidad = d.id_tipo_disponibilidad
                ORDER BY d.fecha DESC, d.hora_inicio
            """, fetch=True)

            for item in self.tree_disponibilidades.get_children():
                self.tree_disponibilidades.delete(item)

            for row in rows:
                usuario = f"{row[2]} {row[3]} --- #{row[1]}"
                tipo = f"{row[5]} --- #{row[4]}"
                fecha = row[6].strftime("%Y-%m-%d") if hasattr(row[6], "strftime") else row[6]
                inicio = row[7].strftime("%H:%M") if hasattr(row[7], "strftime") else row[7]
                fin = row[8].strftime("%H:%M") if hasattr(row[8], "strftime") else row[8]
                self.tree_disponibilidades.insert("", "end", values=(row[0], usuario, tipo, fecha, inicio, fin))

            valores_u = ["Seleccione un usuario"] + list(self.usuarios_combo.keys())
            self.combo_disp_usuario.configure(values=valores_u)

        except Exception as e:
            print(f"Error cargando disponibilidades: {e}")

    def cargar_datos_tipos_disponibilidad(self):
        try:
            rows = self.ejecutar_consulta(
                "SELECT id_tipo_disponibilidad, estado FROM tipos_disponibilidad ORDER BY id_tipo_disponibilidad",
                fetch=True
            )
            self.tipos_disponibilidad_combo = {}
            for row in rows:
                etiqueta = f"{row[1]} --- #{row[0]}"
                self.tipos_disponibilidad_combo[etiqueta] = row[0]
            valores_t = ["Seleccione un tipo"] + list(self.tipos_disponibilidad_combo.keys())
            self.combo_disp_tipo.configure(values=valores_t)
        except Exception as e:
            print(f"Error cargando tipos de disponibilidad: {e}")

    def buscar_usuarios_libres(self):
        try:
            fecha = self.obtener_fecha(self.fecha_busqueda)
            try:
                hora_inicio = datetime.strptime(self.hora_inicio_busqueda.get().strip(), "%H:%M").time()
                hora_fin = datetime.strptime(self.hora_fin_busqueda.get().strip(), "%H:%M").time()
            except ValueError:
                raise ValueError("La hora debe tener formato HH:MM, por ejemplo 14:00.")
            if hora_fin <= hora_inicio:
                raise ValueError("La hora de fin debe ser posterior a la hora de inicio.")

            rango_inicio = f"{fecha} {hora_inicio}"
            rango_fin = f"{fecha} {hora_fin}"

            rows = self.ejecutar_consulta("""
                SELECT u.id_usuario, u.nombre, u.apellido
                FROM usuarios u
                WHERE NOT EXISTS (
                    SELECT 1 FROM eventos e
                    WHERE e.id_usuario_propietario = u.id_usuario
                      AND e.fecha_inicio < %s AND e.fecha_fin > %s
                )
                AND NOT EXISTS (
                    SELECT 1 FROM participaciones p
                    JOIN eventos e ON e.id_evento = p.id_evento
                    WHERE p.id_invitado = u.id_usuario
                      AND e.fecha_inicio < %s AND e.fecha_fin > %s
                )
                AND NOT EXISTS (
                    SELECT 1 FROM disponibilidades d
                    JOIN tipos_disponibilidad t ON t.id_tipo_disponibilidad = d.id_tipo_disponibilidad
                    WHERE d.id_usuario = u.id_usuario
                      AND t.estado <> 'Disponible'
                      AND d.fecha = %s
                      AND d.hora_inicio < %s AND d.hora_fin > %s
                )
                ORDER BY u.nombre, u.apellido
            """, (rango_fin, rango_inicio, rango_fin, rango_inicio, fecha, hora_fin, hora_inicio), fetch=True)

            for item in self.tree_libres.get_children():
                self.tree_libres.delete(item)
            for row in rows:
                self.tree_libres.insert("", "end", values=(row[0], f"{row[1]} {row[2]}"))

            if not rows:
                messagebox.showinfo("Sin resultados", "Nadie está libre en ese rango. Probá con otro horario.")

        except Exception as e:
            messagebox.showerror("No se pudo buscar", str(e))

    # -------------------- EVENTOS RECURRENTES --------------------

    def configurar_pestana_series(self):
        self.crear_encabezado(self.tab_series, "Eventos Recurrentes",
                               "Define series periódicas y genera automáticamente sus ocurrencias.")

        cuerpo = ctk.CTkFrame(self.tab_series, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=10, pady=5)
        cuerpo.grid_columnconfigure(0, weight=3)
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)

        izquierda = ctk.CTkFrame(cuerpo, fg_color="transparent")
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        izquierda.grid_rowconfigure(0, weight=1)
        izquierda.grid_rowconfigure(1, weight=1)
        izquierda.grid_columnconfigure(0, weight=1)

        panel_series = ctk.CTkFrame(izquierda)
        panel_series.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        ctk.CTkLabel(panel_series, text="Series definidas",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=8, pady=(6, 2))
        self.tree_series = self.crear_treeview(
            panel_series,
            ("ID", "Tipo", "Cada", "Inicio", "Fin", "Ocurrencias"),
            (40, 80, 50, 90, 90, 90)
        )
        self.tree_series.bind("<<TreeviewSelect>>", self.cargar_ocurrencias_serie)

        panel_ocurrencias = ctk.CTkFrame(izquierda)
        panel_ocurrencias.grid(row=1, column=0, sticky="nsew")
        ctk.CTkLabel(panel_ocurrencias, text="Ocurrencias de la serie seleccionada",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=8, pady=(6, 2))
        self.tree_ocurrencias = self.crear_treeview(
            panel_ocurrencias,
            ("ID Evento", "Título", "Inicio", "Fin"),
            (70, 160, 130, 130)
        )

        ctk.CTkButton(izquierda, text="🗑 Eliminar serie seleccionada (y sus ocurrencias)",
                      command=self.eliminar_serie, fg_color="#b33939",
                      hover_color="#8f2d2d").grid(row=2, column=0, sticky="ew", pady=(8, 0))

        form = ctk.CTkScrollableFrame(cuerpo, width=300)
        form.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(form, text="Nueva serie de eventos",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 15))

        ctk.CTkLabel(form, text="Usuario").pack(anchor="w", padx=10, pady=(6, 2))
        self.combo_serie_usuario = ctk.CTkComboBox(form, values=["Seleccione un usuario"], state="readonly")
        self.combo_serie_usuario.set("Seleccione un usuario")
        self.combo_serie_usuario.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Categoría").pack(anchor="w", padx=10, pady=(6, 2))
        self.combo_serie_categoria = ctk.CTkComboBox(form, values=["Seleccione una categoría"], state="readonly")
        self.combo_serie_categoria.set("Seleccione una categoría")
        self.combo_serie_categoria.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Título").pack(anchor="w", padx=10, pady=(6, 2))
        self.titulo_serie = ctk.CTkEntry(form, placeholder_text="Ej: Reunión semanal de equipo")
        self.titulo_serie.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Hora inicio (HH:MM)").pack(anchor="w", padx=10, pady=(6, 2))
        self.hora_inicio_serie = ctk.CTkEntry(form, placeholder_text="HH:MM")
        self.hora_inicio_serie.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Hora fin (HH:MM)").pack(anchor="w", padx=10, pady=(6, 2))
        self.hora_fin_serie = ctk.CTkEntry(form, placeholder_text="HH:MM")
        self.hora_fin_serie.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Tipo de periodo").pack(anchor="w", padx=10, pady=(10, 2))
        self.combo_tipo_periodo = ctk.CTkComboBox(form, values=["Dias", "Semanas", "Meses", "Años"], state="readonly")
        self.combo_tipo_periodo.set("Semanas")
        self.combo_tipo_periodo.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Cada cuántas unidades").pack(anchor="w", padx=10, pady=(6, 2))
        self.cantidad_periodo = ctk.CTkEntry(form, placeholder_text="Ej: 1")
        self.cantidad_periodo.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(form, text="Fecha inicio de la serie").pack(anchor="w", padx=10, pady=(10, 2))
        self.fecha_inicio_serie_widget = self.crear_selector_fecha(form)
        self.fecha_inicio_serie_widget.pack(fill="x", padx=10)

        self.serie_indefinida = ctk.CTkCheckBox(form, text="Serie indefinida (sin fecha de fin)",
                                                 command=self.alternar_fecha_fin_serie)
        self.serie_indefinida.pack(anchor="w", padx=10, pady=(10, 4))

        ctk.CTkLabel(form, text="Fecha final de la serie").pack(anchor="w", padx=10, pady=(6, 2))
        self.fecha_fin_serie_widget = self.crear_selector_fecha(form)
        self.fecha_fin_serie_widget.pack(fill="x", padx=10)

        ctk.CTkButton(form, text="⚙️ Generar serie",
                      command=self.generar_serie_eventos).pack(fill="x", padx=10, pady=(18, 5))

        self.limpiar_form_serie()

    def alternar_fecha_fin_serie(self):
        if self.serie_indefinida.get():
            self.fecha_fin_serie_widget.configure(state="disabled")
        else:
            self.fecha_fin_serie_widget.configure(state="normal")

    def limpiar_form_serie(self):
        self.combo_serie_usuario.set("Seleccione un usuario")
        self.combo_serie_categoria.set("Seleccione una categoría")
        self.titulo_serie.delete(0, tk.END)
        self.hora_inicio_serie.delete(0, tk.END); self.hora_inicio_serie.insert(0, "09:00")
        self.hora_fin_serie.delete(0, tk.END); self.hora_fin_serie.insert(0, "10:00")
        self.combo_tipo_periodo.set("Semanas")
        self.cantidad_periodo.delete(0, tk.END); self.cantidad_periodo.insert(0, "1")
        self.establecer_fecha(self.fecha_inicio_serie_widget, datetime.now())
        self.serie_indefinida.deselect()
        self.fecha_fin_serie_widget.configure(state="normal")
        self.establecer_fecha(self.fecha_fin_serie_widget, datetime.now())

    def cargar_ocurrencias_serie(self, _=None):
        sel = self.tree_series.selection()
        for item in self.tree_ocurrencias.get_children():
            self.tree_ocurrencias.delete(item)
        if not sel:
            return
        id_serie = self.tree_series.item(sel[0])["values"][0]
        try:
            rows = self.ejecutar_consulta("""
                SELECT id_evento, titulo, fecha_inicio, fecha_fin
                FROM eventos WHERE id_serie_evento = %s
                ORDER BY fecha_inicio
            """, (id_serie,), fetch=True)
            for row in rows:
                self.tree_ocurrencias.insert("", "end", values=(
                    row[0], row[1], row[2].strftime("%Y-%m-%d %H:%M"), row[3].strftime("%Y-%m-%d %H:%M")))
        except Exception as e:
            print(f"Error cargando ocurrencias: {e}")

    def generar_serie_eventos(self):
        try:
            id_usuario = self.usuarios_combo.get(self.combo_serie_usuario.get())
            id_categoria = self.categorias_combo.get(self.combo_serie_categoria.get())
            titulo = self.titulo_serie.get().strip()
            if id_usuario is None or id_categoria is None or not titulo:
                raise ValueError("Selecciona usuario, categoría y escribe un título.")

            try:
                hora_inicio = datetime.strptime(self.hora_inicio_serie.get().strip(), "%H:%M").time()
                hora_fin = datetime.strptime(self.hora_fin_serie.get().strip(), "%H:%M").time()
            except ValueError:
                raise ValueError("La hora debe tener formato HH:MM.")
            if hora_fin <= hora_inicio:
                raise ValueError("La hora de fin debe ser posterior a la de inicio.")

            tipo_periodo = self.combo_tipo_periodo.get()
            try:
                cantidad = int(self.cantidad_periodo.get().strip())
                if cantidad <= 0:
                    raise ValueError
            except ValueError:
                raise ValueError("La cantidad debe ser un número entero positivo.")

            fecha_inicio = datetime.strptime(self.obtener_fecha(self.fecha_inicio_serie_widget), "%Y-%m-%d").date()
            if self.serie_indefinida.get():
                fecha_fin = None
            else:
                fecha_fin = datetime.strptime(self.obtener_fecha(self.fecha_fin_serie_widget), "%Y-%m-%d").date()
                if fecha_fin < fecha_inicio:
                    raise ValueError("La fecha final no puede ser anterior a la fecha de inicio.")

            fechas = generar_fechas_serie(fecha_inicio, tipo_periodo, cantidad, fecha_fin)

            conn = self.obtener_conexion()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO series_eventos
                        (tipo_periodo, cantidad_unidades_x_repeticion, fecha_inicio_serie, fecha_final_serie)
                        VALUES (%s, %s, %s, %s) RETURNING id_serie_evento
                    """, (tipo_periodo, cantidad, fecha_inicio, fecha_fin))
                    id_serie = cur.fetchone()[0]

                    for f in fechas:
                        inicio_evento = datetime.combine(f, hora_inicio)
                        fin_evento = datetime.combine(f, hora_fin)
                        cur.execute("""
                            INSERT INTO eventos
                            (id_usuario_propietario, id_categoria, titulo, fecha_inicio, fecha_fin, id_serie_evento)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (id_usuario, id_categoria, titulo, inicio_evento, fin_evento, id_serie))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

            self.limpiar_form_serie()
            self.cargar_datos_series()
            self.cargar_datos_eventos()
            messagebox.showinfo("Serie generada", f"Se crearon {len(fechas)} ocurrencias, del "
                                 f"{fechas[0]} al {fechas[-1]}.")

        except Exception as e:
            messagebox.showerror("No se pudo generar la serie", str(e))

    def eliminar_serie(self):
        sel = self.tree_series.selection()
        if not sel:
            return messagebox.showwarning("Selección requerida", "Selecciona una serie.")
        id_serie = self.tree_series.item(sel[0])["values"][0]
        if not messagebox.askyesno("Confirmar", "¿Eliminar esta serie y TODAS sus ocurrencias generadas?"):
            return
        try:
            self.ejecutar_consulta("DELETE FROM series_eventos WHERE id_serie_evento = %s", (id_serie,))
            self.cargar_datos_series()
            self.cargar_datos_eventos()
            for item in self.tree_ocurrencias.get_children():
                self.tree_ocurrencias.delete(item)
            messagebox.showinfo("Eliminada", "Serie y sus ocurrencias eliminadas.")
        except Exception as e:
            messagebox.showerror("No se pudo eliminar", str(e))

    def cargar_datos_series(self):
        try:
            rows = self.ejecutar_consulta("""
                SELECT s.id_serie_evento, s.tipo_periodo, s.cantidad_unidades_x_repeticion,
                       s.fecha_inicio_serie, s.fecha_final_serie, COUNT(e.id_evento)
                FROM series_eventos s
                LEFT JOIN eventos e ON e.id_serie_evento = s.id_serie_evento
                GROUP BY s.id_serie_evento
                ORDER BY s.id_serie_evento DESC
            """, fetch=True)

            for item in self.tree_series.get_children():
                self.tree_series.delete(item)
            for row in rows:
                fin = row[4].strftime("%Y-%m-%d") if row[4] else "Indefinida"
                self.tree_series.insert("", "end", values=(row[0], row[1], row[2], row[3], fin, row[5]))

            valores_u = ["Seleccione un usuario"] + list(self.usuarios_combo.keys())
            self.combo_serie_usuario.configure(values=valores_u)
            valores_c = ["Seleccione una categoría"] + list(self.categorias_combo.keys())
            self.combo_serie_categoria.configure(values=valores_c)
        except Exception as e:
            print(f"Error cargando series: {e}")

    # -------------------- REFRESCO GENERAL --------------------

    def actualizar_todas_las_tablas(self):
        self.cargar_datos_usuarios()
        self.cargar_datos_categorias()
        self.cargar_datos_eventos()
        self.cargar_datos_tipos_disponibilidad()
        self.cargar_datos_disponibilidades()
        self.cargar_datos_series()


if __name__ == "__main__":
    app = AppAgenda()
    app.mainloop()
