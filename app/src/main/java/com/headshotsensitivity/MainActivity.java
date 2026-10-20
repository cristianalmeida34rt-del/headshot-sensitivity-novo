
package com.headshotsensitivity;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.os.BatteryManager;
import android.os.Build;
import android.os.CancellationSignal;
import android.util.DisplayMetrics;
import android.util.Log;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebSettings;
import android.webkit.JavascriptInterface;
import android.graphics.Color;
import android.widget.FrameLayout;

import androidx.credentials.ClearCredentialStateRequest;
import androidx.credentials.Credential;
import androidx.credentials.CredentialManager;
import androidx.credentials.CustomCredential;
import androidx.credentials.GetCredentialRequest;
import androidx.credentials.GetCredentialResponse;
import androidx.credentials.exceptions.ClearCredentialException;
import androidx.credentials.exceptions.GetCredentialException;
import androidx.credentials.exceptions.GetCredentialCancellationException;
import androidx.credentials.exceptions.NoCredentialException;
import androidx.credentials.CredentialManagerCallback;

import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption;
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;

import org.json.JSONObject;

public class MainActivity extends Activity {
    private WebView webView;
    private DeviceBridge deviceBridge;
    private CredentialManager credentialManager;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(5, 5, 5));
        getWindow().setNavigationBarColor(Color.rgb(5, 5, 5));
        getWindow().getDecorView().setSystemUiVisibility(0);
        credentialManager = CredentialManager.create(this);

        FrameLayout layout = new FrameLayout(this);
        layout.setBackgroundColor(Color.rgb(5, 5, 5));
        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(5, 5, 5));
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDefaultTextEncodingName("UTF-8");
        deviceBridge = new DeviceBridge(this);
        webView.addJavascriptInterface(deviceBridge, "AndroidDevice");
        webView.setWebViewClient(new WebViewClient());
        webView.loadUrl("file:///android_asset/index.html");
        layout.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(layout);
    }

    private void runJs(String script) {
        runOnUiThread(() -> {
            if (webView != null) webView.evaluateJavascript(script, null);
        });
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    public final class DeviceBridge {
        private final MainActivity activity;
        private final Context context;
        private final SharedPreferences authPrefs;

        DeviceBridge(MainActivity activity) {
            this.activity = activity;
            this.context = activity.getApplicationContext();
            this.authPrefs = context.getSharedPreferences("google_session", Context.MODE_PRIVATE);
        }

        @JavascriptInterface
        public boolean isGoogleSignedIn() {
            return authPrefs.contains("email");
        }

        @JavascriptInterface
        public String getGoogleAccount() {
            try {
                JSONObject account = new JSONObject();
                account.put("signedIn", isGoogleSignedIn());
                account.put("name", authPrefs.getString("name", ""));
                account.put("email", authPrefs.getString("email", ""));
                return account.toString();
            } catch (Exception error) {
                return "{\"signedIn\":false}";
            }
        }

        @JavascriptInterface
        public void signInWithGoogle() {
            activity.runOnUiThread(() -> beginGoogleSignIn());
        }

        private void beginGoogleSignIn() {
            try {
                String webClientId = activity.getString(R.string.google_web_client_id);
                GetSignInWithGoogleOption googleOption =
                        new GetSignInWithGoogleOption.Builder(webClientId).build();
                GetCredentialRequest request = new GetCredentialRequest.Builder()
                        .addCredentialOption(googleOption)
                        .build();
                credentialManager.getCredentialAsync(
                        activity,
                        request,
                        new CancellationSignal(),
                        command -> activity.runOnUiThread(command),
                        new CredentialManagerCallback<GetCredentialResponse, GetCredentialException>() {
                            @Override
                            public void onResult(GetCredentialResponse result) {
                                handleGoogleCredential(result.getCredential());
                            }

                            @Override
                            public void onError(GetCredentialException error) {
                                String message;
                                String detail = error.getMessage() == null ? "" : error.getMessage().trim();
                                if (detail.length() > 240) detail = detail.substring(0, 240);
                                Log.e("HeadshotGoogle", "Credential Manager falhou: "
                                        + error.getClass().getSimpleName() + " | " + detail, error);
                                if (error instanceof GetCredentialCancellationException) {
                                    message = "O Google fechou a tentativa sem concluir o login. Como você escolheu uma conta, isso também pode ser uma falha OAuth, não um cancelamento manual. Confira o cliente Android (pacote e SHA-1), se os clientes Android e Web estão no mesmo projeto e se sua conta está em Usuários de teste quando o consentimento estiver em modo Teste."
                                            + (detail.isEmpty() ? "" : " Detalhe técnico: " + detail);
                                } else if (error instanceof NoCredentialException) {
                                    message = "Nenhuma conta Google compatível foi encontrada. Adicione a conta ao Android e confira a configuração OAuth.";
                                } else {
                                    message = "Erro Google " + error.getClass().getSimpleName()
                                            + (detail.isEmpty() ? "" : ": " + detail)
                                            + ". Confira os clientes OAuth Android/Web e a conta de teste.";
                                }
                                runJs("onGoogleSignInError(" + JSONObject.quote(message) + ")");
                            }
                        });
            } catch (Exception error) {
                runJs("onGoogleSignInError(\"Não foi possível iniciar o login Google. Verifique a configuração OAuth.\")");
            }
        }

        private void handleGoogleCredential(Credential credential) {
            if (!(credential instanceof CustomCredential)
                    || !GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL.equals(credential.getType())) {
                runJs("onGoogleSignInError(\"O Google retornou um tipo de credencial inesperado. Tente novamente.\")");
                return;
            }
            try {
                GoogleIdTokenCredential googleAccount =
                        GoogleIdTokenCredential.createFrom(((CustomCredential) credential).getData());
                String email = googleAccount.getId();
                String name = googleAccount.getDisplayName();
                String idToken = googleAccount.getIdToken();
                if (email == null || email.trim().isEmpty() || idToken == null || idToken.isEmpty()) {
                    runJs("onGoogleSignInError(\"A resposta do Google não incluiu uma conta válida.\")");
                    return;
                }
                // The ID token is intentionally not persisted or exposed to JavaScript.
                authPrefs.edit().putString("email", email).putString("name", name == null ? "" : name).apply();
                runJs("onGoogleSignInSuccess(" + JSONObject.quote(name == null ? "" : name)
                        + "," + JSONObject.quote(email) + ")");
            } catch (Exception error) {
                runJs("onGoogleSignInError(\"Não foi possível ler a resposta de login do Google. Atualize o Google Play Services e tente de novo.\")");
            }
        }

        @JavascriptInterface
        public void signOutGoogle() {
            authPrefs.edit().clear().apply();
            activity.runOnUiThread(() -> credentialManager.clearCredentialStateAsync(
                    new ClearCredentialStateRequest(),
                    new CancellationSignal(),
                    command -> activity.runOnUiThread(command),
                    new CredentialManagerCallback<Void, ClearCredentialException>() {
                        @Override
                        public void onResult(Void result) {
                            runJs("onGoogleSignOutComplete()");
                        }

                        @Override
                        public void onError(ClearCredentialException error) {
                            // The local app session is cleared even if a provider cannot clear its cache.
                            runJs("onGoogleSignOutComplete()");
                        }
                    }));
        }

        @JavascriptInterface
        public String getDeviceInfo() {
            try {
                DisplayMetrics display = context.getResources().getDisplayMetrics();
                ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
                ActivityManager manager = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
                if (manager != null) manager.getMemoryInfo(memory);
                Intent battery = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
                int batteryPercent = -1;
                boolean charging = false;
                if (battery != null) {
                    int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
                    int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
                    if (level >= 0 && scale > 0) batteryPercent = Math.round(level * 100f / scale);
                    int status = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
                    charging = status == BatteryManager.BATTERY_STATUS_CHARGING
                            || status == BatteryManager.BATTERY_STATUS_FULL;
                }
                JSONObject info = new JSONObject();
                info.put("brand", Build.BRAND);
                info.put("manufacturer", Build.MANUFACTURER);
                info.put("model", Build.MODEL);
                info.put("androidVersion", Build.VERSION.RELEASE);
                info.put("sdk", Build.VERSION.SDK_INT);
                info.put("screenWidth", display.widthPixels);
                info.put("screenHeight", display.heightPixels);
                info.put("densityDpi", display.densityDpi);
                info.put("density", display.density);
                info.put("ramTotalMb", memory.totalMem / (1024L * 1024L));
                info.put("ramAvailableMb", memory.availMem / (1024L * 1024L));
                info.put("batteryPercent", batteryPercent);
                info.put("charging", charging);
                return info.toString();
            } catch (Exception error) {
                return "{}";
            }
        }

        @JavascriptInterface
        public boolean openOfficialUrl(String url) {
            try {
                Uri uri = Uri.parse(url);
                String host = uri.getHost();
                boolean officialHost = "ff.garena.com".equals(host)
                        || "freefiremobile.com".equals(host)
                        || "www.freefiremobile.com".equals(host)
                        || "www.garena.com".equals(host);
                if (!"https".equals(uri.getScheme()) || !officialHost) return false;
                Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(intent);
                return true;
            } catch (Exception error) {
                return false;
            }
        }
    }
}
