"""Un almacén S3 en memoria para las pruebas de las copias de seguridad: sin red."""

import hashlib
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

from almacen.copias import Respuesta


class S3Falso:
    def __init__(self, bucket: str, por_pagina: int = 1000) -> None:
        self.bucket = bucket
        self.por_pagina = por_pagina
        self.existe_bucket = False
        self.objetos: dict[str, tuple[bytes, dict[str, str]]] = {}
        # Tipo, caché y compresión de cada objeto, como los guarda S3 (almacen/reserva.py).
        self.cabeceras: dict[str, dict[str, str]] = {}
        self.peticiones: list[tuple[str, str]] = []
        self.fallos_pendientes = 0

    def __call__(self, peticion: urllib.request.Request) -> Respuesta:
        metodo = peticion.get_method()
        partes = urllib.parse.urlsplit(peticion.full_url)
        if partes.netloc.startswith(f"{self.bucket}."):
            # Dirección anónima (sin firma): el bucket es privado.
            return Respuesta(403, {}, b"AccessDenied")
        ruta = urllib.parse.unquote(partes.path).lstrip("/")
        bucket, _, clave = ruta.partition("/")
        assert bucket == self.bucket
        assert "Authorization" in peticion.headers or "authorization" in {
            k.lower() for k in peticion.headers
        }
        self.peticiones.append((metodo, clave))
        if self.fallos_pendientes:
            self.fallos_pendientes -= 1
            return Respuesta(503, {}, b"SlowDown")
        if not clave:
            return self._bucket(metodo, urllib.parse.parse_qs(partes.query))
        cabeceras = {k.lower(): v for k, v in peticion.header_items()}
        if metodo == "PUT":
            cuerpo = peticion.data
            assert isinstance(cuerpo, bytes)
            assert cabeceras["x-amz-content-sha256"] == hashlib.sha256(cuerpo).hexdigest()
            meta = {k: v for k, v in cabeceras.items() if k.startswith("x-amz-meta-")}
            self.objetos[clave] = (cuerpo, meta)
            self.cabeceras[clave] = {
                k: v
                for k, v in cabeceras.items()
                if k in ("content-type", "cache-control", "content-encoding")
            }
            return Respuesta(200, {}, b"")
        if clave not in self.objetos:
            return Respuesta(404, {}, b"")
        cuerpo, meta = self.objetos[clave]
        # La etiqueta cambia con cada subida, aunque el contenido sea el mismo (como un ETag
        # de subida en partes): así se ve si un objeto se ha vuelto a subir.
        etiqueta = {"etag": f'"{hashlib.md5(cuerpo + str(id(meta)).encode()).hexdigest()}"'}
        if metodo == "HEAD":
            return Respuesta(200, {**meta, **etiqueta}, b"")
        if metodo == "GET":
            return Respuesta(200, {**self.cabeceras.get(clave, {}), **meta, **etiqueta}, cuerpo)
        if metodo == "DELETE":
            del self.objetos[clave]
            self.cabeceras.pop(clave, None)
            return Respuesta(204, {}, b"")
        raise AssertionError(metodo)

    def _bucket(self, metodo: str, consulta: dict[str, list[str]]) -> Respuesta:
        if metodo == "HEAD":
            return Respuesta(200 if self.existe_bucket else 404, {}, b"")
        if metodo == "PUT":
            self.existe_bucket = True
            return Respuesta(200, {}, b"")
        assert metodo == "GET" and consulta["list-type"] == ["2"]
        prefijo = consulta.get("prefix", [""])[0]
        claves = sorted(c for c in self.objetos if c.startswith(prefijo))
        desde = int(consulta.get("continuation-token", ["0"])[0])
        pagina = claves[desde : desde + self.por_pagina]
        truncada = desde + self.por_pagina < len(claves)
        contenidos = "".join(
            f"<Contents><Key>{escape(c)}</Key><Size>{len(self.objetos[c][0])}</Size>"
            # En el listado, el ETag de una subida de una vez: el MD5 del contenido.
            f'<ETag>"{hashlib.md5(self.objetos[c][0]).hexdigest()}"</ETag></Contents>'
            for c in pagina
        )
        siguiente = (
            f"<NextContinuationToken>{desde + self.por_pagina}</NextContinuationToken>"
            if truncada
            else ""
        )
        xml = (
            '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            f"<IsTruncated>{'true' if truncada else 'false'}</IsTruncated>{siguiente}"
            f"{contenidos}</ListBucketResult>"
        )
        return Respuesta(200, {}, xml.encode())
