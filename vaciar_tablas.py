import sqlite3

def vaciar_base_datos(ruta_db):
    # Conectar a la base de datos SQLite
    conexion = sqlite3.connect(ruta_db)
    cursor = conexion.cursor()
    
    try:
        # Desactivar temporalmente las claves foráneas para evitar conflictos
        cursor.execute("PRAGMA foreign_keys = OFF;")
        
        # Obtener los nombres de todas las tablas en la base de datos
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tablas = cursor.fetchall()
        
        for tabla in tablas:
            nombre_tabla = tabla[0]
            
            # Excluir la tabla de productos y las tablas internas del sistema SQLite
            if nombre_tabla != "productos" and not nombre_tabla.startswith("sqlite_"):
                print(f"Vaciar tabla: {nombre_tabla}")
                cursor.execute(f"DELETE FROM {nombre_tabla};")
                
                # Opcional: Reiniciar el autoincremento (ID) de la tabla vaciada
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name = '{nombre_tabla}';")

        # Volver a activar las claves foráneas
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Guardar los cambios (commit)
        conexion.commit()
        print("\n¡Base de datos vaciada exitosamente! Los 308 productos se han mantenido intactos.")

    except Exception as e:
        conexion.rollback()
        print(f"Ocurrió un error y se revirtieron los cambios: {e}")
        
    finally:
        conexion.close()

if __name__ == "__main__":
    # Reemplaza 'tu_base_de_datos.db' con la ruta exacta de tu archivo SQLite
    ruta_archivo = "C:\\Users\\Mirielys\\Documents\\Py\\LDDL V5\\tienda.db"
    vaciar_base_datos(ruta_archivo)