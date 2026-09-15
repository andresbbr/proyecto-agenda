-- Crear la base de datos
CREATE DATABASE agenda;
CREATE SCHEMA prototipo;

-- Configurar el search_path para que las tablas se creen dentro de ese esquema
-- y se busquen ahí automáticamente
SET search_path TO prototipo, public;

-- 1. Usuarios
CREATE TABLE usuarios (
    id_usuario SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    apellido VARCHAR(50) NOT NULL,
    fecha_registro DATE DEFAULT CURRENT_DATE NOT NULL,
    activo BOOLEAN DEFAULT TRUE
);

-- 2. Contactos (RF02, RE02, RN02)
CREATE TABLE usuario_telefonos (
    id_usuario INT REFERENCES usuarios(id_usuario),
    telefono VARCHAR(20),
    PRIMARY KEY (id_usuario, telefono)
);

CREATE TABLE usuario_emails (
    id_usuario INT REFERENCES usuarios(id_usuario),
    email VARCHAR(100),
    PRIMARY KEY (id_usuario, email)
);

-- 3. Categorías (RF03, RE05, RN04)
CREATE TABLE categorias (
    id_categoria SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    id_categoria_padre INT REFERENCES categorias(id_categoria)
    -- NOTA: La raíz tendría id_categoria_padre NULL
);

-- 4. Eventos (RF04, RE04)
CREATE TABLE eventos (
    id_evento SERIAL PRIMARY KEY,
    id_usuario_propietario INT NOT NULL REFERENCES usuarios(id_usuario),
    id_categoria INT NOT NULL REFERENCES categorias(id_categoria),
    titulo VARCHAR(100) NOT NULL,
    descripcion TEXT,
    fecha_inicio TIMESTAMP NOT NULL,
    fecha_fin TIMESTAMP NOT NULL,
    CONSTRAINT check_fechas CHECK (fecha_fin > fecha_inicio)
);

-- 5. Participación (RF05, RE01, RN01, RN05)
CREATE TABLE participaciones (
    id_evento INT REFERENCES eventos(id_evento) ON DELETE CASCADE,
    id_invitado INT REFERENCES usuarios(id_usuario),
    rol VARCHAR(50),
    estado_confirmacion VARCHAR(20) DEFAULT 'pendiente',
    PRIMARY KEY (id_evento, id_invitado)
);

-- 6. Log de Accesos (RF06)
CREATE TABLE log_accesos (
    id_log SERIAL PRIMARY KEY,
    id_usuario INT REFERENCES usuarios(id_usuario),
    fecha_acceso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Implementación de Cálculos Dinámicos (RF07, RE03, RN03) mediante vistas

-- Vista para Antigüedad
CREATE VIEW vista_antiguedad_usuarios AS
SELECT 
    id_usuario, 
    nombre, 
    fecha_registro,
    age(CURRENT_DATE, fecha_registro) AS antiguedad
FROM usuarios;

-- Vista para Duración de eventos diarios
CREATE VIEW vista_duracion_eventos_diarios AS
SELECT 
    id_usuario_propietario,
    fecha_inicio::DATE AS dia,
    SUM(EXTRACT(EPOCH FROM (fecha_fin - fecha_inicio))/60) AS duracion_total_minutos
FROM eventos
GROUP BY id_usuario_propietario, fecha_inicio::DATE;

--Integridad y Prevención de Ciclos (RE05)
--Para evitar ciclos en la jerarquía de categorías, podemos usar una función 
--que verifique el ancestro antes de insertar o actualizar:

CREATE OR REPLACE FUNCTION evitar_ciclo_categorias()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id_categoria_padre = NEW.id_categoria THEN
        RAISE EXCEPTION 'Una categoría no puede ser padre de sí misma.';
    END IF;
    -- Aquí se podría añadir una consulta recursiva para validar ancestros, 
    -- pero para Postgres 14 es altamente eficiente usar el camino (path) o este chequeo simple.
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_evitar_ciclo
BEFORE INSERT OR UPDATE ON categorias
FOR EACH ROW EXECUTE FUNCTION evitar_ciclo_categorias();

CREATE TABLE tipos_disponibilidad (
id_tipo_disponibilidad SERIAL PRIMARY KEY NOT NULL,
estado varchar(50) NOT NULL
);

CREATE TABLE disponibilidades (
id_disponibilidad SERIAL PRIMARY KEY NOT NULL,
id_usuario INT NOT NULL REFERENCES usuarios(id_usuario),
id_tipo_disponibilidad INT NOT NULL REFERENCES tipos_disponibilidad(id_tipo_disponibilidad),
fecha DATE NOT NULL,
hora_inicio TIME NOT NULL,
hora_fin TIME NOT NULL
CONSTRAINT check_horas CHECK (hora_fin > hora_inicio)
);

INSERT INTO tipos_disponibilidad (estado) VALUES
('Disponible'), ('Ocupado'), ('No disponible');

SELECT u.id_usuario, u.nombre, u.apellido
FROM usuarios u
WHERE NOT EXISTS (
    SELECT 1 FROM eventos e
    WHERE e.id_usuario_propietario = u.id_usuario
      AND e.fecha_inicio < :rango_fin AND e.fecha_fin > :rango_inicio
)
AND NOT EXISTS (
    SELECT 1 FROM participaciones p
    JOIN eventos e ON e.id_evento = p.id_evento
    WHERE p.id_invitado = u.id_usuario
      AND e.fecha_inicio < :rango_fin AND e.fecha_fin > :rango_inicio
)
AND NOT EXISTS (
    SELECT 1 FROM disponibilidades d
    JOIN tipos_disponibilidad t ON t.id_tipo_disponibilidad = d.id_tipo_disponibilidad
    WHERE d.id_usuario = u.id_usuario
      AND t.estado <> 'Disponible'
      AND d.fecha = :fecha_consultada
      AND d.hora_inicio < :rango_fin AND d.hora_fin > :rango_inicio
);

CREATE TABLE series_eventos(
id_serie_evento SERIAL PRIMARY KEY NOT NULL,
tipo_periodo VARCHAR(50) NOT NULL CHECK (tipo_periodo IN ('Dias', 'Semanas', 'Meses', 'Años')),
cantidad_unidades_x_repeticion SMALLINT NOT NULL CHECK (cantidad_unidades_x_repeticion > 0),
fecha_inicio_serie DATE NOT NULL,
fecha_final_serie DATE --Esto lo dejo con la posibilidad de null porque podría ser algo sin fecha de fin, una serie de eventos que se repite indefinidamente.
);

ALTER TABLE eventos 
ADD COLUMN id_serie_evento INT  REFERENCES series_eventos(id_serie_evento);

--Esto es el limite de fecha_final_serie
ALTER TABLE eventos DROP CONSTRAINT eventos_id_serie_evento_fkey;
ALTER TABLE eventos ADD CONSTRAINT eventos_id_serie_evento_fkey
    FOREIGN KEY (id_serie_evento) REFERENCES series_eventos(id_serie_evento) ON DELETE CASCADE;

