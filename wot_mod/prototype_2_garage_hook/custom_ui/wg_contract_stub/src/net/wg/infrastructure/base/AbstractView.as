/*
 * Compile-only declaration for the exact client class audited from lobby.swf.
 * This SWC is external at link time and is never packaged in Shotcaller.
 */
package net.wg.infrastructure.base {
    import flash.display.MovieClip;

    public class AbstractView extends MovieClip {
        public function AbstractView() {
            super();
        }

        protected function onPopulate():void {
        }

        protected function onDispose():void {
        }
    }
}
