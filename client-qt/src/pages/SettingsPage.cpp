#include <rakshak/pages/SettingsPage.h>
#include <rakshak/common/Settings.h>

#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QFormLayout>
#include <QtWidgets/QLabel>
#include <QtWidgets/QLineEdit>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QFileDialog>
#include <QtWidgets/QMessageBox>

using namespace rakshak::pages;
using rakshak::backend::ApiClient;
using rakshak::common::Settings;

SettingsPage::SettingsPage(ApiClient* api, QWidget* parent) : QWidget(parent), m_api(api) {
    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(48, 40, 48, 32);
    layout->setSpacing(8);

    auto* title = new QLabel(tr("Settings"), this);
    title->setObjectName("pageTitle");
    layout->addWidget(title);

    auto* form = new QFormLayout();
    form->setSpacing(4);

    auto caption = [this, form](const QString& text) {
        auto* c = new QLabel(text, this);
        c->setProperty("role", "muted");
        c->setWordWrap(true);
        form->addRow(c);
    };

    auto* logPathRow = new QHBoxLayout();
    m_logPathInput = new QLineEdit(this);
    m_logPathInput->setPlaceholderText(tr("optional - leave empty for manual scans/checks only"));
    m_logPathInput->setToolTip(tr("A file to tail continuously in the background. New lines are "
        "auto-scored as they arrive; flagged ones show up in Log Analysis and Recent Activity."));
    m_browseButton = new QPushButton(tr("Browse..."), this);
    logPathRow->addWidget(m_logPathInput, 1);
    logPathRow->addWidget(m_browseButton);
    form->addRow(tr("Log path"), logPathRow);
    caption(tr("Optional. Watches a live log file in the background - new lines get scored "
        "automatically, no need to check them by hand. Manual scans and line-checks work fine "
        "without this set at all."));

    m_apiBaseUrlInput = new QLineEdit(this);
    m_apiBaseUrlInput->setToolTip(tr("Base URL of the FastAPI backend this client talks to."));
    form->addRow(tr("Backend URL"), m_apiBaseUrlInput);
    caption(tr("Must match a backend actually running at that address, e.g. http://127.0.0.1:8080."));

    m_apiKeyInput = new QLineEdit(this);
    m_apiKeyInput->setEchoMode(QLineEdit::Password);
    m_apiKeyInput->setToolTip(tr("Sent as the x-api-key header on every request to the backend."));
    form->addRow(tr("API key"), m_apiKeyInput);
    caption(tr("Must match the backend's RAKSHAK_API_KEY (default \"dev-key\" in local dev)."));

    layout->addLayout(form);
    layout->addSpacing(12);

    auto* buttonRow = new QHBoxLayout();
    m_saveButton = new QPushButton(tr("Save"), this);
    m_saveButton->setProperty("role", "primary");
    m_saveButton->setToolTip(tr("Persist these settings and apply them immediately - no restart needed."));
    m_restoreDefaultsButton = new QPushButton(tr("Restore defaults"), this);
    m_restoreDefaultsButton->setProperty("role", "danger");
    m_restoreDefaultsButton->setToolTip(tr("Reset log path, backend URL, and API key to their defaults."));
    m_testConnectionButton = new QPushButton(tr("Test connection"), this);
    m_testConnectionButton->setToolTip(tr("Pings /health on the backend URL above, using the real live backend."));
    buttonRow->addWidget(m_saveButton);
    buttonRow->addWidget(m_restoreDefaultsButton);
    buttonRow->addWidget(m_testConnectionButton);
    buttonRow->addStretch();
    layout->addLayout(buttonRow);

    m_testResultLabel = new QLabel(this);
    m_testResultLabel->setProperty("role", "muted");
    layout->addWidget(m_testResultLabel);
    layout->addStretch();

    connect(m_browseButton, &QPushButton::clicked, this, &SettingsPage::onBrowseLogPath);
    connect(m_saveButton, &QPushButton::clicked, this, &SettingsPage::onSaveClicked);
    connect(m_restoreDefaultsButton, &QPushButton::clicked, this, &SettingsPage::onRestoreDefaultsClicked);
    connect(m_testConnectionButton, &QPushButton::clicked, this, &SettingsPage::onTestConnectionClicked);

    connect(m_api, &ApiClient::healthChecked, this, [this](bool reachable, const QString& version) {
        m_testResultLabel->setText(reachable
            ? tr("Backend reachable (v%1).").arg(version)
            : tr("Backend unreachable."));
    });

    loadFromSettings();
}

void SettingsPage::loadFromSettings() {
    const auto d = Settings::instance().load();
    m_logPathInput->setText(d.logPath);
    m_apiBaseUrlInput->setText(d.apiBaseUrl);
    m_apiKeyInput->setText(d.apiKey);
}

void SettingsPage::onBrowseLogPath() {
    const auto path = QFileDialog::getOpenFileName(this, tr("Choose a log file to tail"));
    if (path.isEmpty()) return;
    m_logPathInput->setText(path);
}

void SettingsPage::onSaveClicked() {
    rakshak::common::SettingsData d;
    d.logPath = m_logPathInput->text();
    d.apiBaseUrl = m_apiBaseUrlInput->text();
    d.apiKey = m_apiKeyInput->text();
    d.darkMode = Settings::instance().load().darkMode; // not edited on this page
    Settings::instance().save(d);
    m_api->reloadSettings();
    emit statusMessage(tr("Settings saved."), false);
    emit settingsApplied();
}

void SettingsPage::onRestoreDefaultsClicked() {
    const auto reply = QMessageBox::question(this, tr("Restore defaults"),
        tr("Reset log path, backend URL, and API key back to their defaults?"));
    if (reply != QMessageBox::Yes) return;

    const rakshak::common::SettingsData defaults; // struct's own default member initializers
    Settings::instance().save(defaults);
    loadFromSettings();
    m_api->reloadSettings();
    emit statusMessage(tr("Settings restored to defaults."), false);
    emit settingsApplied();
}

void SettingsPage::onTestConnectionClicked() {
    m_testResultLabel->setText(tr("Checking..."));
    m_api->checkHealth();
}
