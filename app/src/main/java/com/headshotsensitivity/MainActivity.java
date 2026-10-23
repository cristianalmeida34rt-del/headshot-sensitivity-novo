package com.headshotsensitivity;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Color;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.util.DisplayMetrics;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import org.json.JSONObject;

public class MainActivity extends Activity {
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(5, 5, 5));
        getWindow().setNavigationBarColor(Color.rgb(5, 5, 5));
        getWindow().getDecorView().setSystemUiVisibility(0);

        // Apaga os dados locais de sessão Google criados por versões antigas do app.
        getSharedPreferences("google_session", MODE_PRIVATE).edit().clear().apply();

        FrameLayout layout = new FrameLayout(this);
        layout.setBackgroundColor(Color.rgb(5, 5, 5));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(5, 5, 5));
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDefaultTextEncodingName("UTF-8");
        webView.addJavascriptInterface(new DeviceBridge(this), "AndroidDevice");
        webView.setWebViewClient(new WebViewClient());
        webView.loadUrl("file:///android_asset/index.html");

        layout.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(layout);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    public static final class DeviceBridge {
        private final Context context;

        DeviceBridge(Context context) {
            this.context = context.getApplicationContext();
        }

        @JavascriptInterface
        public String getDeviceInfo() {
            try {
                DisplayMetrics display = context.getResources().getDisplayMetrics();
                ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
                ActivityManager manager = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
                if (manager != null) manager.getMemoryInfo(memory);

                Intent battery = context.registerReceiver(null,
                        new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
                int batteryPercent = -1;
                boolean charging = false;
                if (battery != null) {
                    int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
                    int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
                    if (level >= 0 && scale > 0) {
                        batteryPercent = Math.round(level * 100f / scale);
                    }
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
        public boolean shareText(String title, String text) {
            try {
                Intent send = new Intent(Intent.ACTION_SEND);
                send.setType("text/plain");
                send.putExtra(Intent.EXTRA_SUBJECT, title);
                send.putExtra(Intent.EXTRA_TEXT, text);
                Intent chooser = Intent.createChooser(send, title);
                chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(chooser);
                return true;
            } catch (Exception error) {
                return false;
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
