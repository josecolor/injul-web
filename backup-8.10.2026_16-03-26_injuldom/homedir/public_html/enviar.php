<?php
/**
 * INJUL – Formulario de Contacto
 * Versión 3: Sincronización de lectura SMTP corregida.
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'msg' => 'Método no permitido.']);
    exit;
}

$nombre   = trim(strip_tags($_POST['nombre']   ?? ''));
$telefono = trim(strip_tags($_POST['telefono'] ?? ''));
$correo   = trim(strip_tags($_POST['correo']   ?? ''));
$servicio = trim(strip_tags($_POST['servicio'] ?? ''));
$mensaje  = trim(strip_tags($_POST['mensaje']  ?? ''));

if (!$nombre || !$correo || !$mensaje) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'msg' => 'Complete los campos obligatorios.']);
    exit;
}

// Configuración de servidor
$smtp_host = 'mail.injul.com.do';
$smtp_port = 465;
$smtp_user = 'contacto@injul.com.do';
$smtp_pass = 'O7]]RcyI+OGzb@Eu';
$para      = 'contacto@injul.com.do';

$asunto_raw = "Consulta web: $servicio - $nombre";
$asunto     = "=?UTF-8?B?" . base64_encode($asunto_raw) . "?=";

$html = "<h3>Nueva consulta desde la web</h3>
         <p><b>Nombre:</b> $nombre <br>
         <b>Correo:</b> $correo <br>
         <b>Teléfono:</b> $telefono <br>
         <b>Servicio:</b> $servicio </p>
         <p><b>Mensaje:</b><br>$mensaje</p>";

function smtp_enviar_final($host, $port, $user, $pass, $para, $asunto, $html) {
    $context = stream_context_create([
        'ssl' => ['verify_peer' => false, 'verify_peer_name' => false, 'allow_self_signed' => true]
    ]);

    $sock = @stream_socket_client("ssl://{$host}:{$port}", $errno, $errstr, 10, STREAM_CLIENT_CONNECT, $context);
    if (!$sock) return "Conexión fallida: $errstr";

    // Función interna para leer todas las líneas de una respuesta SMTP
    $leer = function($s) {
        $data = "";
        while($line = fgets($s, 512)) {
            $data .= $line;
            if(substr($line, 3, 1) == " ") break; // El cuarto caracter es espacio cuando termina la respuesta
        }
        return $data;
    };

    $leer($sock); // Leer banner inicial

    fputs($sock, "EHLO " . ($_SERVER['HTTP_HOST'] ?: "localhost") . "\r\n");
    $leer($sock); // Leer TODAS las líneas del EHLO (aquí estaba el fallo)

    fputs($sock, "AUTH LOGIN\r\n");
    $leer($sock);
    
    fputs($sock, base64_encode($user) . "\r\n");
    $leer($sock);
    
    fputs($sock, base64_encode($pass) . "\r\n");
    $resp_auth = $leer($sock);
    
    if (strpos($resp_auth, '235') === false) return "Error de clave: " . $resp_auth;

    fputs($sock, "MAIL FROM:<$user>\r\n");
    $leer($sock);
    
    fputs($sock, "RCPT TO:<$para>\r\n");
    $leer($sock);
    
    fputs($sock, "DATA\r\n");
    $leer($sock);

    $hdrs  = "From: INJUL Web <$user>\r\n";
    $hdrs .= "To: $para\r\n";
    $hdrs .= "MIME-Version: 1.0\r\n";
    $hdrs .= "Content-Type: text/html; charset=UTF-8\r\n";
    $hdrs .= "Subject: $asunto\r\n\r\n";

    fputs($sock, $hdrs . $html . "\r\n.\r\n");
    $resp_final = $leer($sock);
    
    fputs($sock, "QUIT\r\n");
    fclose($sock);

    return (strpos($resp_final, '250') !== false) ? true : $resp_final;
}

$resultado = smtp_enviar_final($smtp_host, $smtp_port, $smtp_user, $smtp_pass, $para, $asunto, $html);

if ($resultado === true) {
    echo json_encode(['ok' => true, 'msg' => '¡Mensaje enviado con éxito!']);
} else {
    http_response_code(500);
    echo json_encode(['ok' => false, 'msg' => 'Fallo: ' . $resultado]);
}