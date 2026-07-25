#include <QtWidgets/QApplication>
#include <QtGui/QIcon>
#include "rakshak/MainWindow.h"

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    app.setWindowIcon(QIcon(":/icons/logo-shield.svg"));

    // MainWindow applies the initial theme (light/dark, from Settings) on
    // construction, and can flip it live via its sidebar toggle.
    MainWindow window;
    window.show();
    return app.exec();
}
