package com.nanomed.daily;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Message;
import android.view.ViewGroup;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

/**
 * 纳米日报：一个全屏网页壳，打开就是追踪网页。
 * 数据更新靠网页本身，App 不用重装。
 */
public class MainActivity extends Activity {

    private static final String HOME = "https://hongrui023.github.io/nanomed-daily/";
    private static final String HOST = "hongrui023.github.io";

    private WebView web;
    private SwipeRefreshLayout swipe;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        swipe = new SwipeRefreshLayout(this);
        swipe.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(swipe);

        web = new WebView(getApplicationContext());
        web.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        swipe.addView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setSupportZoom(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setSupportMultipleWindows(true);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setUserAgentString(s.getUserAgentString() + " NanomedDaily/1.0");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                String u = req.getUrl() == null ? "" : req.getUrl().toString();
                if (u.contains(HOST)) return false;
                if (u.startsWith("http://") || u.startsWith("https://")) {
                    openOutside(u);
                    return true;
                }
                return false;
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                swipe.setRefreshing(false);
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onCreateWindow(WebView v, boolean dialog, boolean gesture, Message msg) {
                WebView nw = new WebView(MainActivity.this);
                nw.setWebViewClient(new WebViewClient() {
                    @Override
                    public boolean shouldOverrideUrlLoading(WebView v2, WebResourceRequest req) {
                        if (req.getUrl() != null) openOutside(req.getUrl().toString());
                        return true;
                    }
                });
                if (msg != null && msg.obj instanceof WebView.WebViewTransport) {
                    ((WebView.WebViewTransport) msg.obj).setWebView(nw);
                    msg.sendToTarget();
                    return true;
                }
                return false;
            }
        });

        web.setDownloadListener((url, ua, cd, mime, len) -> openOutside(url));

        swipe.setColorSchemeResources(android.R.color.holo_blue_bright,
                android.R.color.holo_green_light, android.R.color.holo_orange_light);
        swipe.setOnRefreshListener(() -> web.reload());

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(HOME);
        }
    }

    private void openOutside(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception e) {
            Toast.makeText(this, "打不开链接：" + url, Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        if (web != null) web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (web != null) web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) web.onResume();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
