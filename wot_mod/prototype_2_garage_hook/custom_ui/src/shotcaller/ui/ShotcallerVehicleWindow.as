package shotcaller.ui {
    import flash.display.MovieClip;
    import flash.display.Loader;
    import flash.display.Sprite;
    import flash.display.GradientType;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.events.IOErrorEvent;
    import flash.events.SecurityErrorEvent;
    import flash.geom.Rectangle;
    import flash.geom.Matrix;
    import flash.net.URLRequest;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;
    import net.wg.infrastructure.base.AbstractView;

    public final class ShotcallerVehicleWindow extends AbstractView {
        private const W:Number = 440;
        private const H:Number = 640;
        // Header ends at y=138; the viewport begins at 154, leaving a 16 px gap.
        private const VIEW_Y:Number = 154;
        private const VIEW_H:Number = 406;
        private const CONTENT_X:Number = 16;
        private const CONTENT_TOP:Number = 8;
        private const FOOTER_PADDING:Number = 16;
        private const FOOTER_GAP:Number = 8;
        private const FOOTER_BUTTONS:int = 4;
        // Deliberately subdued background treatment; all interactive content is
        // added above this Loader and remains fully readable/clickable.
        private const WATERMARK_ALPHA:Number = 0.14;
        private const WATERMARK_MAX_SIZE:Number = 300;
        private var titleField:TextField;
        private var statusField:TextField;
        private var content:Sprite;
        private var viewport:Sprite;
        private var thumb:Sprite;
        private var scrollTrack:Sprite;
        private var previousButton:Sprite;
        private var nextButton:Sprite;
        private var closeButton:Sprite;
        private var settingsButton:Sprite;
        private var dragging:Boolean = false;
        private var dragDX:Number = 0;
        private var dragDY:Number = 0;
        private var pendingData:String = null;
        private var watermark:Loader;
        public var onClose:Function;
        public var onPrevious:Function;
        public var onNext:Function;
        public var onSettings:Function;
        public var onPosition:Function;

        public function ShotcallerVehicleWindow() {
            trace("[shotcaller] custom window constructor");
            addEventListener(Event.ADDED_TO_STAGE, onAdded);
        }

        override protected function onPopulate():void {
            super.onPopulate();
            trace("[shotcaller] custom window DAAPI population");
        }

        override protected function onDispose():void {
            trace("[shotcaller] custom window dispose");
            if (viewport != null) {
                viewport.removeEventListener(MouseEvent.MOUSE_WHEEL, onWheel);
            }
            if (thumb != null) {
                thumb.removeEventListener(MouseEvent.MOUSE_DOWN, onThumbDown);
            }
            removeEventListener(MouseEvent.MOUSE_DOWN, onTitleDown);
            super.onDispose();
        }

        private function onAdded(event:Event):void {
            removeEventListener(Event.ADDED_TO_STAGE, onAdded);
            buildStaticLayout();
        }

        private function buildStaticLayout():void {
            gradient(0,0,W,H,0x171914,0x20231C); graphics.lineStyle(1,0x625B48);graphics.drawRect(.5,.5,W-1,H-1);graphics.lineStyle(1,0x8A7958);graphics.drawRect(3.5,3.5,W-7,H-7);
            gradient(4,4,W-8,30,0x34362F,0x242620); graphics.beginFill(0xD98B34);graphics.drawRect(5,33,W-10,1);graphics.endFill();
            titleField = text(16, 8, W - 32, 22, 16, 0xE8E2D5, true);
            titleField.text = "Shotcaller vehicle history";
            statusField = text(16, 46, W - 32, 92, 13, 0xB8B1A3, false);
            viewport = new Sprite(); viewport.x = 16; viewport.y = VIEW_Y;
            viewport.scrollRect = new Rectangle(0, 0, W - 52, VIEW_H);
            addChild(viewport);
            content = new Sprite(); content.x = 0; content.y = CONTENT_TOP;
            viewport.addChild(content); viewport.addEventListener(MouseEvent.MOUSE_WHEEL, onWheel);
            scrollTrack = new Sprite(); scrollTrack.graphics.beginFill(0x11130F); scrollTrack.graphics.drawRect(0, 0, 10, VIEW_H); scrollTrack.graphics.endFill(); scrollTrack.x = W - 24; scrollTrack.y = VIEW_Y; addChild(scrollTrack);
            thumb = new Sprite(); thumb.graphics.beginFill(0x8A7958); thumb.graphics.drawRect(0, 0, 10, 60); thumb.graphics.endFill(); thumb.x = W - 24; thumb.y = VIEW_Y; addChild(thumb);
            thumb.addEventListener(MouseEvent.MOUSE_DOWN, onThumbDown);
            var buttonWidth:Number=Math.floor((W-FOOTER_PADDING*2-FOOTER_GAP*(FOOTER_BUTTONS-1))/FOOTER_BUTTONS);
            var buttonY:Number=580;
            previousButton = addButton("Previous", FOOTER_PADDING, buttonY, buttonWidth); nextButton = addButton("Next", FOOTER_PADDING+buttonWidth+FOOTER_GAP, buttonY, buttonWidth);
            settingsButton = addButton("Settings", FOOTER_PADDING+(buttonWidth+FOOTER_GAP)*2, buttonY, buttonWidth);
            settingsButton.removeEventListener(MouseEvent.CLICK, onButton);
            settingsButton.addEventListener(MouseEvent.CLICK, onSettingsClick);
            trace("[shotcaller] settings button constructed");
            closeButton = addButton("Close", FOOTER_PADDING+(buttonWidth+FOOTER_GAP)*3, buttonY, buttonWidth);
            addEventListener(MouseEvent.MOUSE_DOWN, onTitleDown);
            trace("[shotcaller] history layout: headerBottom=138 viewportY=" + VIEW_Y + " firstHeadingY=" + CONTENT_TOP + " gap=" + (VIEW_Y - 138));
        }

        private function text(xv:Number, yv:Number, width:Number, height:Number, size:Number, color:uint, bold:Boolean):TextField {
            var field:TextField = new TextField(); field.x = xv; field.y = yv; field.width = width; field.height = height;
            field.defaultTextFormat = new TextFormat("$TextFont", size, color, bold); field.selectable = false; field.multiline = true;
            addChild(field); return field;
        }

        private function gradient(xv:Number,yv:Number,wv:Number,hv:Number,top:uint,bottom:uint):void {var m:Matrix=new Matrix();m.createGradientBox(wv,hv,Math.PI/2,xv,yv);graphics.beginGradientFill(GradientType.LINEAR,[top,bottom],[1,1],[0,255],m);graphics.drawRect(xv,yv,wv,hv);graphics.endFill();}
        private function addButton(label:String, xv:Number, yv:Number, width:Number):Sprite {
            var button:Sprite = new Sprite(); button.name = label; button.x = xv; button.y = yv;
            var m:Matrix=new Matrix();m.createGradientBox(width,34,Math.PI/2,0,0);button.graphics.beginGradientFill(GradientType.LINEAR,[0x45483D,0x252820],[1,1],[0,255],m);button.graphics.drawRect(0,0,width,34);button.graphics.endFill();button.graphics.lineStyle(1,0x8A7958);button.graphics.drawRect(.5,.5,width-1,33);
            var labelField:TextField = new TextField(); labelField.width = width; labelField.height = 28; labelField.y = 5; labelField.selectable = false;
            labelField.defaultTextFormat = new TextFormat("$TextFont", 13, 0xE8E2D5, true, null, null, null, null, "center"); labelField.text = label; button.addChild(labelField);
            button.addEventListener(MouseEvent.CLICK, onButton); addChild(button); return button;
        }

        public function as_setHistoryHeader(data:String):void { if (statusField != null) statusField.htmlText = data; }
        public function as_beginHistoryRows():void { setInformationalLayout(false); if (content != null) { clearContent(); content.y = CONTENT_TOP; } }
        public function as_addHistoryHeading(label:String):void {
            if (label == null || label.indexOf("SHOTCALLER") >= 0 || label.indexOf("[") >= 0) return;
            var yv:Number = content.height; trace("[shotcaller] history heading input: label=" + label + " length=" + label.length); addHeadingRow(label, yv);
        }
        public function as_addHistoryVehicle(label:String, battles:Number=0, wins:Number=-1, isAce:Boolean=false):void { addVehicleRow(label, Math.max(0, int(battles)), int(wins), isAce, content.height); }
        public function as_finishHistoryRows():void { updateScroll(true); visible = true; }

        public function as_setPosition(px:Number, py:Number):void {
            if (stage == null) return;
            x = Math.max(0, Math.min(stage.stageWidth - W, px));
            y = Math.max(0, Math.min(stage.stageHeight - H, py));
        }

        public function as_setWatermark(uri:String):void {
            if (watermark != null) { try { watermark.close(); } catch (ignore:Error) {} if (contains(watermark)) removeChild(watermark); watermark = null; }
            if (uri == null || uri.length == 0) return;
            watermark = new Loader(); watermark.mouseEnabled = false; watermark.mouseChildren = false; watermark.alpha = WATERMARK_ALPHA;
            watermark.contentLoaderInfo.addEventListener(Event.COMPLETE, watermarkReady); watermark.contentLoaderInfo.addEventListener(IOErrorEvent.IO_ERROR, watermarkFailed); watermark.contentLoaderInfo.addEventListener(SecurityErrorEvent.SECURITY_ERROR, watermarkFailed);
            try { watermark.load(new URLRequest(uri)); } catch (error:Error) { watermark = null; }
        }
        private function watermarkReady(event:Event):void { if (watermark == null || watermark.content == null) return; var scale:Number = Math.min(WATERMARK_MAX_SIZE / Math.max(1, watermark.content.width), WATERMARK_MAX_SIZE / Math.max(1, watermark.content.height)); watermark.scaleX = watermark.scaleY = scale; watermark.x = (W - watermark.width) * .5; watermark.y = VIEW_Y + (VIEW_H - watermark.height) * .5; addChildAt(watermark, 0); }
        private function watermarkFailed(event:Event):void { if (watermark != null && contains(watermark)) removeChild(watermark); watermark = null; }

        public function as_setMessageState(contextLabel:String, titleLine:String, detailLine:String):void {
            if (statusField == null) return;
            statusField.text = contextLabel + "\n" + titleLine + "\n" + detailLine;
            clearContent(); setInformationalLayout(true); updateScroll(true); visible = true;
            trace("[shotcaller] history message state received");
        }

        private function clearContent():void { while (content != null && content.numChildren > 0) content.removeChildAt(0); }
        private function addVehicleRow(label:String, battles:int, wins:int, isAce:Boolean, yv:Number):void { var nameField:TextField = new TextField(); nameField.x = CONTENT_X; nameField.y = yv; nameField.width = W - 202; nameField.height = 20; nameField.defaultTextFormat = new TextFormat("_sans", 13, 0xFFFFFF, false); nameField.embedFonts = false; nameField.multiline = false; nameField.wordWrap = false; nameField.selectable = false; nameField.text = label; content.addChild(nameField); if(isAce) addAceBadge(nameField, yv); var statsField:TextField = new TextField(); statsField.x = W - 178; statsField.y = yv; statsField.width = 118; statsField.height = 20; statsField.defaultTextFormat = new TextFormat("_sans", 12, 0xB8B1A3, false, null, null, null, null, "right"); statsField.embedFonts = false; statsField.multiline = false; statsField.wordWrap = false; statsField.selectable = false; statsField.text = formatWinRate(wins, battles) + " / " + formatBattles(battles); content.addChild(statsField); }
        private function addAceBadge(nameField:TextField, yv:Number):void { var badge:Sprite=new Sprite(); badge.mouseEnabled=false; badge.mouseChildren=false; badge.graphics.beginFill(0xC99A3D); badge.graphics.drawCircle(0,0,7); badge.graphics.endFill(); badge.graphics.lineStyle(1,0xF1D57A); badge.graphics.drawCircle(0,0,7); badge.x=Math.min(W-190,nameField.x+Math.min(nameField.textWidth+12,nameField.width-8)); badge.y=yv+10; var a:TextField=new TextField();a.x=-4;a.y=-7;a.width=8;a.height=13;a.selectable=false;a.mouseEnabled=false;a.defaultTextFormat=new TextFormat("_sans",9,0x211B10,true,null,null,null,null,"center");a.text="A";badge.addChild(a);content.addChild(badge); }
        private function formatBattles(value:int):String { var raw:String = String(Math.max(0, value)); var out:String = ""; var n:int = raw.length; for (var i:int = 0; i < n; i++) { if (i > 0 && (n - i) % 3 == 0) out += ","; out += raw.charAt(i); } return out; }
        private function formatWinRate(wins:int, battles:int):String { if (battles <= 0 || wins < 0 || wins > battles) return "—"; return (Math.round((1000.0 * wins / battles)) / 10.0).toFixed(1) + "%"; }
        private function addHeadingRow(label:String, yv:Number):void {
            var plate:Sprite = new Sprite(); plate.x = 8; plate.y = yv; plate.graphics.beginFill(0x303428); plate.graphics.drawRect(0,0,W-68,24); plate.graphics.endFill(); plate.graphics.beginFill(0xD98B34); plate.graphics.drawRect(0,23,W-68,1); plate.graphics.endFill(); content.addChild(plate);
            var heading:TextField = new TextField(); heading.x = 24; heading.y = yv + 3; heading.width = W - 92; heading.height = 20; heading.defaultTextFormat = new TextFormat("_sans", 13, 0xE8E2D5, true); heading.embedFonts = false; heading.autoSize = TextFieldAutoSize.NONE; heading.multiline = false; heading.wordWrap = false; heading.selectable = false; heading.text = label; content.addChild(heading);
            var statsHeading:TextField = new TextField(); statsHeading.x = W - 178; statsHeading.y = yv + 3; statsHeading.width = 118; statsHeading.height = 20; statsHeading.defaultTextFormat = new TextFormat("_sans", 11, 0xE8E2D5, true, null, null, null, null, "right"); statsHeading.embedFonts = false; statsHeading.selectable = false; statsHeading.text = "WR / Battles"; content.addChild(statsHeading);
            trace("[shotcaller] history heading rendered: text=" + heading.text + " length=" + heading.text.length + " fieldX=" + heading.x + " effectiveX=" + (viewport.x + content.x + heading.x));
        }

        private function onWheel(event:MouseEvent):void { content.y = clamp(content.y + event.delta * 24); updateThumb(); }
        private function onThumbDown(event:MouseEvent):void { stage.addEventListener(MouseEvent.MOUSE_MOVE, onThumbMove); stage.addEventListener(MouseEvent.MOUSE_UP, onThumbUp); }
        private function onThumbMove(event:MouseEvent):void { thumb.y = Math.max(VIEW_Y, Math.min(VIEW_Y + VIEW_H - thumb.height, mouseY)); var range:Number = Math.max(1, VIEW_H - thumb.height); content.y = CONTENT_TOP - (thumb.y - VIEW_Y) / range * Math.max(0, content.height - (VIEW_H - CONTENT_TOP)); }
        private function onThumbUp(event:MouseEvent):void { stage.removeEventListener(MouseEvent.MOUSE_MOVE, onThumbMove); stage.removeEventListener(MouseEvent.MOUSE_UP, onThumbUp); }
        private function clamp(value:Number):Number { return Math.min(CONTENT_TOP, Math.max(CONTENT_TOP - Math.max(0, content.height - (VIEW_H - CONTENT_TOP)), value)); }
        private function updateScroll(reset:Boolean=true):void { if(reset) content.y = CONTENT_TOP; thumb.visible = content.height > (VIEW_H - CONTENT_TOP); scrollTrack.visible = thumb.visible; updateThumb(); }
        private function setInformationalLayout(value:Boolean):void { if (previousButton == null) return; previousButton.visible = !value; nextButton.visible = !value; if (value) { settingsButton.x = 48; settingsButton.width = 156; closeButton.x = 220; closeButton.width = 156; thumb.visible = false; scrollTrack.visible = false; } else { var bw:Number = Math.floor((W-FOOTER_PADDING*2-FOOTER_GAP*(FOOTER_BUTTONS-1))/FOOTER_BUTTONS); settingsButton.x = FOOTER_PADDING+(bw+FOOTER_GAP)*2; settingsButton.width = bw; closeButton.x = FOOTER_PADDING+(bw+FOOTER_GAP)*3; closeButton.width = bw; } }
        private function updateThumb():void { if (!thumb.visible) return; thumb.height = Math.max(32, VIEW_H * VIEW_H / content.height); thumb.y = VIEW_Y + ((CONTENT_TOP-content.y) / Math.max(1, content.height - (VIEW_H-CONTENT_TOP))) * (VIEW_H - thumb.height); }
        private function onTitleDown(event:MouseEvent):void {
            if (mouseY > 34 || event.target == thumb) return;
            dragging = true; dragDX = mouseX; dragDY = mouseY;
            stage.addEventListener(MouseEvent.MOUSE_MOVE, onTitleMove);
            stage.addEventListener(MouseEvent.MOUSE_UP, onTitleUp);
        }
        private function onTitleMove(event:MouseEvent):void {
            if (!dragging || stage == null) return;
            x = Math.max(0, Math.min(stage.stageWidth - W, stage.mouseX - dragDX));
            y = Math.max(0, Math.min(stage.stageHeight - H, stage.mouseY - dragDY));
        }
        private function onTitleUp(event:MouseEvent):void {
            dragging = false;
            if (stage != null) { stage.removeEventListener(MouseEvent.MOUSE_MOVE, onTitleMove); stage.removeEventListener(MouseEvent.MOUSE_UP, onTitleUp); }
            if (onPosition != null) onPosition(x, y);
        }
        private function onButton(event:MouseEvent):void {
            var action:String = event.currentTarget.name;
            if (action == "Close" && onClose != null) onClose();
            else if (action == "Previous" && onPrevious != null) onPrevious();
            else if (action == "Next" && onNext != null) onNext();
        }
        private function onSettingsClick(event:MouseEvent):void {
            trace("[shotcaller] settings click received");
            if (onSettings != null) onSettings();
            trace("[shotcaller] settings callback invoked");
        }
    }
}
